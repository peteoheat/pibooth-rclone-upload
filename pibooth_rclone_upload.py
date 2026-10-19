"""
pibooth_rclone_upload

PiBooth plugin that uploads captured pictures to an rclone remote.
Written against pibooth 2.1.0.

Configuration
-------------
The options live in the [RCLONE_UPLOAD] section of pibooth.cfg. That section is
created automatically the first time the plugin is loaded (see
``_ensure_config_section``). Two settings are required and have no default:

    RCLONE_remote   rclone remote name (see 'rclone listremotes')
    RCLONE_bucket   bucket / top-level folder on that remote

If a required setting is missing, or the remote is not known to rclone for the
user running pibooth, an error naming the offending setting is logged and the
plugin deactivates itself. pibooth itself keeps running.
"""

__version__ = "1.5.0"

import io
import os
import shlex
import shutil
import subprocess
import threading
from pathlib import Path
from typing import List, Optional

import pibooth
from pibooth.utils import LOGGER

SECTION = "RCLONE_UPLOAD"
RCLONE_MANIFEST = ".rclone_uploaded_manifest.txt"

# Files that change over time: re-uploaded on every run, never put in the manifest.
SIDECAR_FILES = ("thumbs.json", "gallery.html")

# Only one rclone job at a time (per-picture uploads vs. the exit upload).
_upload_lock = threading.Lock()

# (option, default, description, menu label, menu choices)
# A menu label makes the option editable in pibooth's Settings menu; None hides it.
# menu choices: a list gives a selector, a string gives a text input.
OPTIONS = [
    ("RCLONE_enabled", True, "Enable uploading pictures with rclone",
     "Upload with rclone", ["True", "False"]),
    ("RCLONE_remote", "", "Required: rclone remote name, as shown by 'rclone listremotes' (without the colon)",
     "Remote name", ""),
    ("RCLONE_bucket", "", "Required: bucket / top-level folder on the remote",
     "Bucket name", ""),
    ("RCLONE_subdir", "", "(Optional) Sub-folder inside the bucket (ex: 'some-event-name')",
     "Sub-folder (optional)", ""),
    ("RCLONE_local_path", "", "Folder to upload from. Leave empty to use pibooth's [GENERAL] directory. "
                              "A relative path is resolved against that directory",
     None, None),
    ("RCLONE_rclone_args", "--transfers=4 --checkers=8 --retries=3",
     "Extra rclone arguments (ex: --config /home/pibooth/.config/rclone/rclone.conf)",
     None, None),
    ("RCLONE_dry_run", False, "Only log the rclone commands, do not run them",
     "Dry run (log only)", ["True", "False"]),
    ("RCLONE_file_extensions", ".jpg,.jpeg,.png,.gif,.mp4,.json,.html",
     "Comma separated file extensions to upload", None, None),
    ("RCLONE_upload_on_exit", True, "Upload anything still pending when pibooth exits", None, None),
    ("RCLONE_bulk_on_exit", False,
     "On exit, run one 'rclone copy' of the whole folder instead of per-file uploads", None, None),
    ("RCLONE_manifest_name", RCLONE_MANIFEST,
     "File (inside the picture folder) that records uploaded files", None, None),
    ("RCLONE_timeout_per_file", 120, "Timeout in seconds for a single file upload", None, None),
    ("RCLONE_timeout_bulk", 300, "Timeout in seconds for the bulk copy on exit", None, None),
    ("RCLONE_include_qrcodes", True, "Also upload QR code images", None, None),
    ("RCLONE_qrcode_suffix", "_qrcode", "QR code file name suffix (before the extension)", None, None),
    ("RCLONE_qrcode_ext", ".png", "QR code file extension", None, None),
]

_DEFAULTS = {name: default for name, default, _d, _m, _c in OPTIONS}


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

def _ensure_config_section(cfg):
    """Create the plugin section in an existing pibooth.cfg if it is missing.

    pibooth only writes plugin options into pibooth.cfg on its very first launch
    or when the Settings menu is saved, so a plugin installed later would never
    appear in the file. Append the section (defaults only) so it can be edited
    with 'pibooth --config'. Nothing else in the file is touched.
    """
    filename = getattr(cfg, "filename", None)
    if not filename or not os.path.isfile(filename):
        return  # first pibooth launch: pibooth generates the whole file itself
    if cfg.has_section(SECTION):
        return
    try:
        with io.open(filename, "a", encoding="utf-8") as fp:
            fp.write("\n[{}]\n".format(SECTION))
            for name, default, description, _menu, _choices in OPTIONS:
                fp.write("# {}\n{} = {}\n\n".format(description, name, default))
    except OSError as exc:
        LOGGER.warning("rclone: could not add the [%s] section to '%s': %s", SECTION, filename, exc)
        return
    LOGGER.info("rclone: added the [%s] section to '%s'. Set RCLONE_remote and RCLONE_bucket, "
                "then restart pibooth", SECTION, filename)


@pibooth.hookimpl
def pibooth_configure(cfg):
    """Declare the plugin options and make sure they are present in pibooth.cfg.

    PiConfigParser.add_option signature is:
        add_option(section, option, default, description, menu_name=None, menu_choices=None)
    """
    for name, default, description, menu_name, menu_choices in OPTIONS:
        cfg.add_option(SECTION, name, default, description, menu_name, menu_choices)
    _ensure_config_section(cfg)


def _get_str(cfg, name: str) -> str:
    return cfg.get(SECTION, name).strip().strip('"').strip()


def _get_bool(cfg, name: str) -> bool:
    raw = _get_str(cfg, name).lower()
    if raw in ("true", "yes", "on", "1"):
        return True
    if raw in ("false", "no", "off", "0"):
        return False
    LOGGER.warning("rclone: invalid value '%s' for [%s][%s] (expected True/False), using %s",
                   raw, SECTION, name, _DEFAULTS[name])
    return bool(_DEFAULTS[name])


def _get_int(cfg, name: str) -> int:
    raw = _get_str(cfg, name)
    try:
        value = int(raw)
        if value <= 0:
            raise ValueError(raw)
        return value
    except ValueError:
        LOGGER.warning("rclone: invalid value '%s' for [%s][%s] (expected a positive number), using %s",
                       raw, SECTION, name, _DEFAULTS[name])
        return int(_DEFAULTS[name])


def _resolve_folders(cfg, local_path: str) -> List[Path]:
    """Work out which folder(s) to upload from.

    pibooth has no ``app.directory`` / ``app.output_dir`` attribute: the picture
    folder(s) come from the [GENERAL] ``directory`` option, which can hold
    several paths, hence ``gettuple``.
    """
    pibooth_dirs = [Path(p).expanduser().absolute()
                    for p in cfg.gettuple("GENERAL", "directory", "path") if p]

    local_path = local_path.strip()
    if not local_path:
        return pibooth_dirs

    lp = Path(local_path).expanduser()
    if lp.is_absolute():
        return [lp]
    if pibooth_dirs:
        return [d / lp for d in pibooth_dirs]
    return [Path.home() / lp]


def _read_settings(cfg) -> dict:
    """Read every option. Bad optional values fall back to their default."""
    args_raw = _get_str(cfg, "RCLONE_rclone_args")
    try:
        args = shlex.split(args_raw)
    except ValueError as exc:
        LOGGER.warning("rclone: cannot parse [%s][RCLONE_rclone_args] (%s), using the default", SECTION, exc)
        args = shlex.split(_DEFAULTS["RCLONE_rclone_args"])

    try:
        folders = _resolve_folders(cfg, _get_str(cfg, "RCLONE_local_path"))
    except Exception as exc:
        LOGGER.warning("rclone: cannot determine the picture folder: %s", exc)
        folders = []

    return {
        "enabled": _get_bool(cfg, "RCLONE_enabled"),
        "remote": _get_str(cfg, "RCLONE_remote").rstrip(":"),
        "bucket": _get_str(cfg, "RCLONE_bucket"),
        "subdir": _get_str(cfg, "RCLONE_subdir"),
        "folders": folders,
        "args": args,
        "dry_run": _get_bool(cfg, "RCLONE_dry_run"),
        "extensions": [x.strip().lower()
                       for x in _get_str(cfg, "RCLONE_file_extensions").split(",") if x.strip()],
        "upload_on_exit": _get_bool(cfg, "RCLONE_upload_on_exit"),
        "bulk_on_exit": _get_bool(cfg, "RCLONE_bulk_on_exit"),
        "manifest_name": _get_str(cfg, "RCLONE_manifest_name") or RCLONE_MANIFEST,
        "timeout_per_file": _get_int(cfg, "RCLONE_timeout_per_file"),
        "timeout_bulk": _get_int(cfg, "RCLONE_timeout_bulk"),
        "include_qrcodes": _get_bool(cfg, "RCLONE_include_qrcodes"),
        "qrcode_suffix": _get_str(cfg, "RCLONE_qrcode_suffix"),
        "qrcode_ext": _get_str(cfg, "RCLONE_qrcode_ext").lower(),
    }


def _missing_settings(settings: dict) -> List[str]:
    """Describe every required setting that is not filled in."""
    problems = []
    if not settings["remote"]:
        problems.append("rclone remote not defined in [{}][RCLONE_remote]".format(SECTION))
    if not settings["bucket"]:
        problems.append("bucket name not defined in [{}][RCLONE_bucket]".format(SECTION))
    if not settings["folders"]:
        problems.append("no picture folder found: check [GENERAL][directory] "
                        "or [{}][RCLONE_local_path]".format(SECTION))
    return problems


def _check_rclone(settings: dict) -> Optional[str]:
    """Return a description of what is wrong with rclone or the remote, or None if usable."""
    if shutil.which("rclone") is None:
        return "'rclone' executable not found in PATH"
    try:
        result = subprocess.run(["rclone"] + settings["args"] + ["listremotes"],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
    except subprocess.TimeoutExpired:
        return "'rclone listremotes' timed out"
    except OSError as exc:
        return "cannot run rclone: {}".format(exc)
    if result.returncode != 0:
        return "'rclone listremotes' failed: {}".format(result.stderr.decode(errors="replace").strip())

    remotes = {line.strip().rstrip(":") for line in result.stdout.decode(errors="replace").splitlines()
               if line.strip()}
    if settings["remote"] not in remotes:
        return ("remote '{}' from [{}][RCLONE_remote] is not in the rclone config of the user running "
                "pibooth (remotes found: {}). Run 'rclone listremotes' and 'rclone config file' as that "
                "user, or pass --config in [{}][RCLONE_rclone_args]".format(
                    settings["remote"], SECTION, ", ".join(sorted(remotes)) or "none", SECTION))
    return None


@pibooth.hookimpl
def pibooth_startup(cfg, app):
    """Validate the configuration once and keep it on the app object.

    Never raise from here: an exception in pibooth_startup takes the whole
    photobooth down, so on any problem the plugin just deactivates itself.
    """
    app.rclone_cfg = {"enabled": False}
    try:
        settings = _read_settings(cfg)
        if not settings["enabled"]:
            LOGGER.info("rclone: uploading disabled in [%s][RCLONE_enabled]", SECTION)
            return

        problems = _missing_settings(settings)
        if not problems:
            rclone_problem = _check_rclone(settings)
            if rclone_problem:
                problems.append(rclone_problem)
        if problems:
            for problem in problems:
                LOGGER.error("rclone: %s, uploading deactivated", problem)
            return
    except Exception as exc:
        LOGGER.error("rclone: unexpected error while reading the configuration, uploading deactivated: %s", exc)
        return

    app.rclone_cfg = settings
    LOGGER.info("rclone: uploading %s -> %s", ", ".join(str(f) for f in settings["folders"]), _dest(settings))


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _dest(settings: dict) -> str:
    parts = [p.strip("/") for p in (settings["bucket"], settings["subdir"]) if p.strip("/")]
    return f"{settings['remote']}:" + "/".join(parts)


def _read_manifest(path: Path) -> set:
    try:
        return set(path.read_text().splitlines()) if path.exists() else set()
    except Exception:
        return set()


def _append_manifest(path: Path, name: str):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as f:
            f.write(name + "\n")
    except Exception:
        LOGGER.warning("rclone: failed to update manifest %s", path)


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:  # file moved meanwhile (e.g. picture "forgotten")
        return 0.0


def _run_rclone_copyto(src: Path, dest: str, args: List[str], dry_run: bool, timeout: int) -> bool:
    full_dest = f"{dest.rstrip('/')}/{src.name}"
    cmd = ["rclone"] + args + ["copyto", str(src), full_dest]
    if dry_run:
        LOGGER.info("rclone: dry-run: %s", " ".join(shlex.quote(a) for a in cmd))
        return True
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        if result.returncode == 0:
            LOGGER.info("rclone: uploaded %s", src.name)
            return True
        LOGGER.warning("rclone: failed to upload %s: %s", src.name, result.stderr.decode(errors="replace").strip())
        return False
    except Exception as exc:
        LOGGER.warning("rclone: exception uploading %s: %s", src.name, exc)
        return False


def _upload_folder(folder: Path, settings: dict):
    if not folder.is_dir():
        LOGGER.warning("rclone: local path does not exist: %s", folder)
        return

    dest = _dest(settings)
    manifest = folder / settings["manifest_name"]
    uploaded = _read_manifest(manifest)
    skip = set(SIDECAR_FILES) | {settings["manifest_name"]}

    files = sorted((f for f in folder.glob("*") if f.is_file()), key=_mtime)

    qr_tail = (settings["qrcode_suffix"] + settings["qrcode_ext"]).lower()
    candidates = []
    for f in files:
        if f.name in skip or f.name in uploaded:
            continue
        is_qrcode = settings["include_qrcodes"] and f.name.lower().endswith(qr_tail)
        if f.suffix.lower() in settings["extensions"] or is_qrcode:
            candidates.append(f)

    # Gallery helper files change constantly, so always push the latest copy.
    for name in SIDECAR_FILES:
        f = folder / name
        if f.exists():
            _run_rclone_copyto(f, dest, settings["args"], settings["dry_run"], settings["timeout_per_file"])

    for f in candidates:
        ok = _run_rclone_copyto(f, dest, settings["args"], settings["dry_run"], settings["timeout_per_file"])
        # A dry run must not mark files as uploaded.
        if ok and not settings["dry_run"]:
            _append_manifest(manifest, f.name)


def _upload_files(app, reason: str):
    settings = getattr(app, "rclone_cfg", None)
    if not settings or not settings.get("enabled"):
        return
    with _upload_lock:
        LOGGER.debug("rclone: upload pass (%s)", reason)
        for folder in settings["folders"]:
            try:
                _upload_folder(folder, settings)
            except Exception as exc:
                LOGGER.warning("rclone: upload pass failed for %s: %s", folder, exc)


def _bulk_copy(settings: dict):
    dest = _dest(settings)
    with _upload_lock:
        for folder in settings["folders"]:
            if not folder.is_dir():
                LOGGER.warning("rclone: local path does not exist: %s", folder)
                continue
            cmd = (["rclone"] + settings["args"] + ["copy", f"{folder}/", dest,
                   # never publish "forgotten" pictures, raw captures or the manifest
                   "--exclude", "/forget/**",
                   "--exclude", "/raw/**",
                   "--exclude", f"/{settings['manifest_name']}"])
            if settings["dry_run"]:
                LOGGER.info("rclone: dry-run bulk copy: %s", " ".join(shlex.quote(a) for a in cmd))
                continue
            try:
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                        timeout=settings["timeout_bulk"])
                if result.returncode == 0:
                    LOGGER.info("rclone: bulk copy of %s complete", folder)
                else:
                    LOGGER.warning("rclone: bulk copy of %s failed: %s", folder,
                                   result.stderr.decode(errors="replace").strip())
            except Exception as exc:
                LOGGER.warning("rclone: bulk copy of %s failed: %s", folder, exc)


# --------------------------------------------------------------------------- #
# Hooks
# --------------------------------------------------------------------------- #

@pibooth.hookimpl
def state_finish_enter(app):
    """Upload in the background once a picture has been kept.

    'finish' is entered after the 'print' state, where the user can "forget" a
    picture (it is moved to the 'forget' sub-folder). By the time we get here a
    forgotten picture is no longer in the folder, so it is never uploaded.
    """
    if not getattr(app, "rclone_cfg", {}).get("enabled"):
        return
    threading.Thread(target=_upload_files, args=(app, "capture"), daemon=True).start()


@pibooth.hookimpl
def pibooth_cleanup(app):
    """Final upload on exit.

    Runs synchronously: a daemon thread would be killed as soon as the
    interpreter exits, cutting the upload short.
    """
    settings = getattr(app, "rclone_cfg", None)
    if not settings or not settings.get("enabled") or not settings.get("upload_on_exit"):
        return
    try:
        if settings["bulk_on_exit"]:
            _bulk_copy(settings)
        else:
            _upload_files(app, "exit")
    except Exception as exc:
        LOGGER.warning("rclone: exit upload failed: %s", exc)

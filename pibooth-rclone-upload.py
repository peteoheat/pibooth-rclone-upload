"""
pibooth-rclone-upload.py

Version: 1.2.6-config-hook-corrected

PiBooth plugin to upload capture files to an rclone remote.
"""

__version__ = "1.2.6-config-hook-corrected"

import shlex
import subprocess
import threading
from pathlib import Path
from typing import List, Set

import pibooth
from pibooth.utils import LOGGER

RCLONE_SECTION = "RCLONE_UPLOAD"
RCLONE_MANIFEST = ".rclone_uploaded_manifest.txt"

@pibooth.hookimpl
def pibooth_configure(cfg):
    if not cfg.has_section(RCLONE_SECTION):
        cfg.add_section(RCLONE_SECTION)

    cfg.add_option(RCLONE_SECTION, "RCLONE_enabled", "True", bool)
    cfg.add_option(RCLONE_SECTION, "RCLONE_remote", "pibooth-cloudflare", str)
    cfg.add_option(RCLONE_SECTION, "RCLONE_bucket", "partyselfie", str)
    cfg.add_option(RCLONE_SECTION, "RCLONE_subdir", "pibooth", str)
    cfg.add_option(RCLONE_SECTION, "RCLONE_local_path", "Pictures", str)
    cfg.add_option(RCLONE_SECTION, "RCLONE_rclone_args", "--transfers=4 --checkers=8 --retries=3", str)
    cfg.add_option(RCLONE_SECTION, "RCLONE_dry_run", "False", bool)
    cfg.add_option(RCLONE_SECTION, "RCLONE_file_extensions", ".jpg,.jpeg,.png,.gif,.mp4,.json,.html", str)
    cfg.add_option(RCLONE_SECTION, "RCLONE_upload_on_exit", "True", bool)
    cfg.add_option(RCLONE_SECTION, "RCLONE_bulk_on_exit", "False", bool)
    cfg.add_option(RCLONE_SECTION, "RCLONE_manifest_name", RCLONE_MANIFEST, str)
    cfg.add_option(RCLONE_SECTION, "RCLONE_timeout_per_file", "120", int)
    cfg.add_option(RCLONE_SECTION, "RCLONE_timeout_bulk", "300", int)
    cfg.add_option(RCLONE_SECTION, "RCLONE_include_qrcodes", "True", bool)
    cfg.add_option(RCLONE_SECTION, "RCLONE_qrcode_suffix", "_qrcode", str)
    cfg.add_option(RCLONE_SECTION, "RCLONE_qrcode_ext", ".png", str)

@pibooth.hookimpl
def pibooth_startup(cfg, app):
    get = lambda key, typ: cfg.getboolean(RCLONE_SECTION, key) if typ is bool else \
                           cfg.getint(RCLONE_SECTION, key) if typ is int else \
                           cfg.get(RCLONE_SECTION, key)

    app.rclone_cfg = {
        "enabled": get("RCLONE_enabled", bool),
        "remote": get("RCLONE_remote", str),
        "bucket": get("RCLONE_bucket", str),
        "subdir": get("RCLONE_subdir", str),
        "local_path": get("RCLONE_local_path", str),
        "args": shlex.split(get("RCLONE_rclone_args", str)),
        "dry_run": get("RCLONE_dry_run", bool),
        "extensions": [x.strip().lower() for x in get("RCLONE_file_extensions", str).split(",")],
        "upload_on_exit": get("RCLONE_upload_on_exit", bool),
        "bulk_on_exit": get("RCLONE_bulk_on_exit", bool),
        "manifest_name": get("RCLONE_manifest_name", str),
        "timeout_per_file": get("RCLONE_timeout_per_file", int),
        "timeout_bulk": get("RCLONE_timeout_bulk", int),
        "include_qrcodes": get("RCLONE_include_qrcodes", bool),
        "qrcode_suffix": get("RCLONE_qrcode_suffix", str),
        "qrcode_ext": get("RCLONE_qrcode_ext", str),
    }

    lp = Path(app.rclone_cfg["local_path"])
    app.rclone_cfg["local_path_abs"] = lp if lp.is_absolute() else Path(app.output_dir) / lp

def _read_manifest(path: Path) -> Set[str]:
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
        else:
            LOGGER.warning("rclone: failed to upload %s: %s", src.name, result.stderr.decode().strip())
            return False
    except Exception as exc:
        LOGGER.warning("rclone: exception uploading %s: %s", src.name, exc)
        return False

def _upload_files(app, reason: str):
    cfg = app.rclone_cfg
    if not cfg.get("enabled", True):
        return
    folder = cfg["local_path_abs"]
    if not folder.exists():
        LOGGER.warning("rclone: local path does not exist: %s", folder)
        return

    dest = f"{cfg['remote']}:{cfg['bucket']}/{cfg['subdir']}".rstrip("/")
    manifest = folder / cfg["manifest_name"]
    uploaded = _read_manifest(manifest)

    files = sorted(folder.glob("*"), key=lambda f: f.stat().st_mtime)
    candidates = [f for f in files if f.suffix.lower() in cfg["extensions"] and f.name not in uploaded]

    if cfg["include_qrcodes"]:
        suffix = cfg["qrcode_suffix"]
        ext = cfg["qrcode_ext"].lower()
        qrcodes = [f for f in files if f.name.lower().endswith(suffix + ext)]
        candidates.extend([f for f in qrcodes if f.name not in uploaded])

    thumbs_json = folder / "thumbs.json"
    gallery_html = folder / "gallery.html"
    for f in [thumbs_json, gallery_html]:
        if f.exists():
            _run_rclone_copyto(f, dest, cfg["args"], cfg["dry_run"], cfg["timeout_per_file"])

    for f in candidates:
        if _run_rclone_copyto(f, dest, cfg["args"], cfg["dry_run"], cfg["timeout_per_file"]):
            _append_manifest(manifest, f.name)

@pibooth.hookimpl
def state_processing_exit(app):
    threading.Thread(target=_upload_files, args=(app, "capture"), daemon=True).start()

@pibooth.hookimpl
def pibooth_cleanup(app):
    cfg = app.rclone_cfg
    if not cfg.get("upload_on_exit", False):
        return

    def _worker():
        if cfg.get("bulk_on_exit", False):
            src = str(cfg["local_path_abs"]) + "/"
            dest = f"{cfg['remote']}:{cfg['bucket']}/{cfg['subdir']}".rstrip("/")
            cmd = ["rclone"] + cfg["args"] + ["copy", src, dest]
            if cfg["dry_run"]:
                LOGGER.info("rclone: dry-run bulk copy: %s", " ".join(shlex.quote(a) for a in cmd))
                return
            try:
                subprocess.run(cmd, timeout=cfg["timeout_bulk"])
                LOGGER.info("rclone: bulk copy complete")
            except Exception as exc:
                LOGGER.warning("rclone: bulk copy failed: %s", exc)
        else:
            _upload_files(app, "exit")

    threading.Thread(target=_worker, daemon=True).start()

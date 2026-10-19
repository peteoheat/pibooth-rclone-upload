# CLAUDE.md

## Project

`pibooth-rclone-upload` is a single-file [pibooth](https://github.com/pibooth/pibooth) plugin (`pibooth_rclone_upload.py`, written against pibooth 2.1.0) that uploads captured pictures, GIFs, videos, QR codes and gallery sidecar files to any rclone remote by shelling out to the `rclone` CLI. Designed to work alongside the author's pibooth-qrcode and pibooth-gallery plugins. MIT licensed.

Repo contents: `pibooth_rclone_upload.py` (all code), `pyproject.toml` (setuptools packaging), `README.md` (also the PyPI long description), `CHANGELOG.md`, `LICENSE`. There is no test suite, linter or CI. The plugin is published on PyPI as `pibooth-rclone-upload` and registers itself with pibooth through the `pibooth` entry point group in `pyproject.toml`, so users do not set `[GENERAL] plugins`. The version lives only in `__version__` in the plugin file (currently 1.5.0); `pyproject.toml` reads it dynamically. Bump it and add a `CHANGELOG.md` entry for each release.

## Running / testing

- The plugin imports `pibooth` and cannot run standalone. It needs pibooth installed (typically on a Raspberry Pi) with `rclone` on `PATH` and a configured remote.
- Manual testing: set `RCLONE_dry_run = True` in `pibooth.cfg` to log rclone commands without executing them. Test the remote with plain `rclone` on the command line first (README stresses this).
- Quick syntax check on any machine: `python -m py_compile pibooth_rclone_upload.py`.
- Local install for testing: `pip install -e .` in the pibooth environment.

## Releasing to PyPI

1. Bump `__version__` and update `CHANGELOG.md` and the README if options changed.
2. `python -m pip install --upgrade build twine`, then `python -m build` (creates `dist/`).
3. `python -m twine check dist/*`.
4. Test first: `python -m twine upload --repository testpypi dist/*`.
5. Publish: `python -m twine upload dist/*` (use a PyPI API token; username `__token__`). A version can never be re-uploaded, so always bump.

## Architecture

Pibooth hooks (all in the one file):

- `pibooth_configure(cfg)`: registers every entry of the `OPTIONS` table via `cfg.add_option(...)` under section `[RCLONE]`, then `_ensure_config_section` appends the section (with defaults and descriptions) to an existing `pibooth.cfg` if missing, since pibooth only writes plugin options on first launch or Settings-menu save.
- `pibooth_startup(cfg, app)`: reads and validates settings (`_read_settings`, `_missing_settings`, `_check_rclone` which runs `rclone listremotes`). The resulting dict is stored on `app.rclone_cfg`. On any problem it logs an error and leaves `{"enabled": False}`.
- `state_finish_enter(app)`: starts a daemon thread running `_upload_files(app, "capture")`. `finish` comes after the `print` state, where "forgotten" pictures have already been moved out, so they are never uploaded.
- `pibooth_cleanup(app)`: final upload on exit, run synchronously (a daemon thread would be killed at interpreter exit). Uses `_bulk_copy` (one `rclone copy`, excluding `/forget/**`, `/raw/**` and the manifest) if `RCLONE_bulk_on_exit`, otherwise `_upload_files`.

Upload logic:

- `_upload_folder` globs the picture folder (non-recursive), sorts by mtime, skips files already in the manifest, and selects files by extension or QR-code suffix+extension. Each file is sent with `rclone copyto`.
- `SIDECAR_FILES` (`thumbs.json`, `gallery.html`) change constantly: they are re-uploaded every pass and never recorded in the manifest.
- The manifest (`.rclone_uploaded_manifest.txt` by default) lives in the picture folder, one filename per line, appended only after a successful non-dry-run upload.
- `_upload_lock` serialises rclone jobs between per-picture and exit uploads.
- Picture folders come from pibooth's `[GENERAL] directory` (a tuple, via `cfg.gettuple`) unless `RCLONE_local_path` overrides it (relative paths resolve against each pibooth dir).
- Destination is `remote:bucket[/subdir]` (`_dest`). `RCLONE_remote` and `RCLONE_bucket` are required and have no default.

## Conventions and gotchas

- Never raise from `pibooth_startup`: an exception there takes the whole photobooth down. Log and deactivate instead. Likewise the upload paths catch and log exceptions rather than propagate.
- All log messages use the `"rclone: ..."` prefix via `pibooth.utils.LOGGER`.
- Adding an option: add a tuple to `OPTIONS` `(name, default, description, menu label or None, menu choices or None)`, read it in `_read_settings` with `_get_str/_get_bool/_get_int` (bad optional values fall back to the default in `_DEFAULTS`), and document it in the README.
- Keep `README.md` in sync with the code (option defaults, required settings, startup validation).
- Dry runs must never touch the manifest.
- Dev environment is Windows; the target runtime is Linux (Raspberry Pi), so don't use Windows-only APIs in the plugin.

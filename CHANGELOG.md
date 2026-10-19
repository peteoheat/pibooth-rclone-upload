# Changelog

## 1.5.0

- Now packaged for PyPI: `pip install pibooth-rclone-upload`. pibooth discovers the
  plugin automatically through its `pibooth` entry point, so nothing needs to be
  added to `[GENERAL] plugins`.
- The module is renamed from `pibooth-rclone-upload.py` to `pibooth_rclone_upload.py`
  (a hyphen is not a valid Python module name). Users who loaded the file by path
  must remove that path from `plugins` after installing from PyPI.
- The `pibooth.cfg` section is renamed from `[RCLONE_UPLOAD]` to `[RCLONE]`. Rename the
  header of an existing section; the option names are unchanged.

## 1.4.0

- Last release distributed as a single file loaded through `[GENERAL] plugins`.

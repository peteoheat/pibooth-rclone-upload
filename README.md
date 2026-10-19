# pibooth-rclone-upload

[![PyPI](https://img.shields.io/pypi/v/pibooth-rclone-upload)](https://pypi.org/project/pibooth-rclone-upload/)
[![License: MIT](https://img.shields.io/pypi/l/pibooth-rclone-upload)](https://github.com/peteoheat/pibooth-rclone-upload/blob/main/LICENSE)

A plugin for [pibooth](https://github.com/pibooth/pibooth) that automatically
uploads captured photos, GIFs, videos, QR codes, and gallery metadata to any
[rclone](https://rclone.org) remote. The benefit of using this plugin is that it
makes your pibooth storage agnostic: you can upload your images to any storage
supported by rclone.

The plugin is designed for reliability, resumability, and unattended operation
during photobooth events. It supports per-file uploads, bulk uploads, manifest
tracking, QR code inclusion, and configurable timeouts. Uploads run in the
background without blocking the booth UI.

It is designed to work alongside my pibooth-qrcode and pibooth-gallery modules.

## Pre-requisites

This plugin depends on an existing [rclone](https://rclone.org) installation.

Before using `pibooth-rclone-upload` you must:

1. **Install rclone on your system in your preferred way**, for example:

       sudo apt install rclone

2. **Create and configure at least one rclone remote**, using:

       rclone config

   You must define a remote that the plugin can upload files to. The plugin does
   not create or configure remotes automatically.

If rclone is not installed or no remote is configured, uploads will fail.

**Please test your rclone and remote from the command line before continuing
with the plugin. If your remote doesn't work at the command line, it won't work
from the plugin.**

## Features

- Uploads captured files to any rclone remote (S3, Cloudflare R2, Google Drive,
  Dropbox, etc.)
- Per-file uploads during booth operation
- Optional bulk upload on exit
- Manifest file to prevent duplicate uploads
- Uploads gallery metadata (`thumbs.json` and `gallery.html`)
- Optional QR code uploads with configurable suffix and extension
- Threaded uploads to avoid blocking pibooth
- Dry-run mode for safe testing
- Customisable rclone arguments, timeouts, and file extensions

## Installation

Install into the same Python environment as pibooth:

    pip install pibooth-rclone-upload

pibooth finds installed plugins automatically through its `pibooth` entry point,
so nothing needs to be added to the `plugins` option. The next time pibooth
starts, the plugin is loaded.

To upgrade:

    pip install --upgrade pibooth-rclone-upload

To remove it:

    pip uninstall pibooth-rclone-upload

### Raspberry Pi OS (Bookworm and Trixie)

Recent Raspberry Pi OS releases mark the system Python as externally managed
(PEP 668), so a bare `pip install` fails with `error: externally-managed-environment`.
Do not work around this with `--break-system-packages`. Install the plugin into
the same environment as pibooth instead:

- **pibooth in a virtual environment** (recommended): use that environment's
  `pip` directly, for example

      ~/venv/bin/pip install pibooth-rclone-upload

  or activate it first (`source ~/venv/bin/activate`).
- **pibooth installed with pipx**:

      pipx inject pibooth pibooth-rclone-upload

- **pibooth installed with `--break-system-packages` or from apt**: the plugin
  has to go in the same place. If you have not set up a virtual environment
  yet, create one with `python3 -m venv --system-site-packages ~/venv`, install
  both `pibooth` and `pibooth-rclone-upload` with `~/venv/bin/pip`, and run
  pibooth from `~/venv/bin/pibooth`.

Check where pibooth lives with `which pibooth`; the plugin must be installed
into that environment.

### Upgrading from a version before 1.5.0

Earlier versions were a single file loaded through the `plugins` option of
`[GENERAL]` in `pibooth.cfg`. After installing from PyPI, **remove the path to
`pibooth-rclone-upload.py` from that option**, otherwise the plugin is loaded
twice. The section in `pibooth.cfg` is now named `[RCLONE]` (it was `[RCLONE_UPLOAD]`): **rename the header of your existing section** to `[RCLONE]`, otherwise the old settings are ignored and an empty `[RCLONE]` section is added. The option names are unchanged.

### Installing from source

    git clone https://github.com/peteoheat/pibooth-rclone-upload
    pip install ./pibooth-rclone-upload

## Configuration

The plugin automatically adds a `[RCLONE]` section (with default values)
to your existing `pibooth.cfg` the first time it is loaded. Edit it with
`pibooth --config` and restart pibooth.

Two settings are **required** and have no default: `RCLONE_remote` and
`RCLONE_bucket`. If either is missing, if no picture folder can be found, or if
the remote is not known to rclone for the user running pibooth, an error naming
the problem is logged and the plugin deactivates itself. pibooth keeps running.
The settings are checked once at startup.

All available configuration options are listed below.

- `RCLONE_enabled` (bool, default: `True`): Enable or disable the plugin.

- `RCLONE_remote` (str, **required**, no default): Name of the rclone remote, as shown by `rclone listremotes` (without the
  trailing colon).

- `RCLONE_bucket` (str, **required**, no default): Bucket or top-level directory on the remote.

- `RCLONE_subdir` (str, default: empty): Optional subdirectory inside the bucket (e.g. an event name).

- `RCLONE_local_path` (str, default: empty): Folder to upload from. Leave empty to use pibooth's `[GENERAL] directory`
  (which may list several folders). A relative path is resolved against that
  directory.

- `RCLONE_rclone_args` (str, default: `--transfers=4 --checkers=8 --retries=3`): Additional rclone arguments, e.g.
  `--config /home/pibooth/.config/rclone/rclone.conf` if pibooth runs as a
  different user from the one who ran `rclone config`.

- `RCLONE_dry_run` (bool, default: `False`): Log actions without uploading.

- `RCLONE_file_extensions` (str, default: `.jpg,.jpeg,.png,.gif,.mp4,.json,.html`): Comma-separated list of file extensions to upload.

- `RCLONE_upload_on_exit` (bool, default: `True`): Upload remaining files when pibooth exits.

- `RCLONE_bulk_on_exit` (bool, default: `False`): Perform a single bulk `rclone copy` on exit.

- `RCLONE_manifest_name` (str, default: `.rclone_uploaded_manifest.txt`): Manifest file (inside the picture folder) used to track uploaded files.

- `RCLONE_timeout_per_file` (int, default: `120`): Timeout (seconds) for each file upload.

- `RCLONE_timeout_bulk` (int, default: `300`): Timeout (seconds) for bulk upload.

- `RCLONE_include_qrcodes` (bool, default: `True`): Upload QR code images.

- `RCLONE_qrcode_suffix` (str, default: `_qrcode`): Suffix used to identify QR code files.

- `RCLONE_qrcode_ext` (str, default: `.png`): File extension for QR code images.

## Upload behaviour

### During booth operation

After each capture, the plugin:

- Scans the output folder
- Detects new files matching configured extensions (and QR codes)
- Uploads them individually using `rclone copyto`
- Records successful uploads in the manifest file
- Always re-uploads `thumbs.json` and `gallery.html`, which change constantly,
  and never records them in the manifest

Uploads run in a background thread to avoid blocking the UI. Pictures
"forgotten" on the print screen are moved out of the folder before the upload
starts, so they are never uploaded.

### On exit

Two modes are available:

**1. Bulk mode** (`RCLONE_bulk_on_exit = True`)

    rclone copy <local_path>/ <remote>:<bucket>/<subdir>

The `forget/` and `raw/` sub-folders and the manifest file are excluded.

**2. Per-file mode** (default)

Uploads any remaining files individually.

## Manifest file

The manifest file:

- Prevents re-uploading files already sent
- Lives inside the local output folder
- Is appended to after each successful upload
- Is created automatically if missing

Deleting the manifest forces all files to be re-uploaded.

## Dry run mode

Enable:

    RCLONE_dry_run = True

This logs all upload commands without executing them. The manifest is never
updated during a dry run.

## Troubleshooting

**The plugin is not loaded at all**

- Make sure it is installed in the same Python environment that runs pibooth
  (`pip show pibooth-rclone-upload`)
- If you upgraded from a version before 1.5.0, remove the old path from
  `[GENERAL] plugins`

**Uploads not happening**

- Ensure `RCLONE_enabled = True`
- Confirm `rclone` is installed and in `PATH`
- Verify the remote name using `rclone listremotes`, running it as the user that
  runs pibooth
- Check the pibooth log: a missing `RCLONE_remote` / `RCLONE_bucket` or an
  unknown remote deactivates the plugin with an error message

**Files not being detected**

- Check `RCLONE_file_extensions`
- Inspect the manifest file

**QR codes not uploading**

- Ensure `RCLONE_include_qrcodes = True`
- Confirm suffix and extension match your QR generator

**Bulk upload fails**

- Increase `RCLONE_timeout_bulk`
- Test manually:

      rclone copy <local> <remote>

## Example configuration

    [RCLONE]
    RCLONE_enabled = True
    RCLONE_remote = pibooth-cloudflare
    RCLONE_bucket = partyselfie
    RCLONE_subdir = event-2025
    RCLONE_local_path =
    RCLONE_rclone_args = --transfers=4 --checkers=8 --retries=3
    RCLONE_upload_on_exit = True
    RCLONE_bulk_on_exit = False
    RCLONE_include_qrcodes = True

## Contributing

Pull requests and feature suggestions are welcome at
<https://github.com/peteoheat/pibooth-rclone-upload>.

## License

MIT License. See [LICENSE](LICENSE).

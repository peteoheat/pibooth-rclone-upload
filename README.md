pibooth-rclone-upload
=====================

A plugin for `pibooth <https://github.com/pibooth/pibooth>`_ that automatically
uploads captured photos, GIFs, videos, QR codes, and gallery metadata to any
`rclone <https://rclone.org>`_ remote.

The plugin is designed for reliability, resumability, and unattended operation
during events. It supports per-file uploads, bulk uploads, manifest tracking,
QR code inclusion, and configurable timeouts. Uploads run in the background
without blocking the booth UI.

It is designed to work alongside my pibooth-qrcode and pibooth-gallery modules.

Pre-requisites
--------------

This plugin depends on an existing `rclone <https://rclone.org>`_ installation.

Before using ``pibooth-rclone-upload`` you must:

1. **Install rclone** on your system  
   (e.g., ``sudo apt install rclone`` on Raspberry Pi OS)

2. **Create and configure at least one rclone remote**  
   using the command:

   .. code-block:: bash

       rclone config

   You must define a remote (e.g., ``pibooth-cloudflare``) that the plugin
   can upload files to. The plugin does not create or configure remotes
   automatically.

If rclone is not installed or no remote is configured, uploads will fail.

Features
--------

- Uploads captured files to any rclone remote (S3, Cloudflare R2, Google Drive,
  Dropbox, etc.)
- Per-file uploads during booth operation
- Optional bulk upload on exit
- Manifest file to prevent duplicate uploads
- Uploads gallery metadata (``thumbs.json`` and ``gallery.html``)
- Optional QR code uploads with configurable suffix and extension
- Threaded uploads to avoid blocking pibooth
- Dry-run mode for safe testing
- Customisable rclone arguments, timeouts, and file extensions

Installation
------------

Install via pip:

.. code-block:: bash

    pip install pibooth-rclone-upload

Or install manually:

.. code-block:: bash

    git clone https://github.com/peteoheat/pibooth-rclone-upload
    cd pibooth-rclone-upload
    pip install .

Ensure ``rclone`` is installed and configured:

.. code-block:: bash

    sudo apt install rclone
    rclone config

Configuration
-------------

The plugin automatically adds a ``[RCLONE_UPLOAD]`` section to your
``pibooth.cfg`` on first run.

All available configuration options are listed below.

``RCLONE_enabled`` (bool, default: ``True``)
    Enable or disable the plugin.

``RCLONE_remote`` (str, default: ``pibooth-cloudflare``)
    Name of the rclone remote.

``RCLONE_bucket`` (str, default: ``partyselfie``)
    Bucket or top-level directory on the remote.

``RCLONE_subdir`` (str, default: ``pibooth``)
    Subdirectory inside the bucket.

``RCLONE_local_path`` (str, default: ``Pictures``)
    Local path where pibooth stores output files.

``RCLONE_rclone_args`` (str, default: ``--transfers=4 --checkers=8 --retries=3``)
    Additional rclone arguments.

``RCLONE_dry_run`` (bool, default: ``False``)
    Log actions without uploading.

``RCLONE_file_extensions`` (str, default: ``.jpg,.jpeg,.png,.gif,.mp4,.json,.html``)
    Comma-separated list of file extensions to upload.

``RCLONE_upload_on_exit`` (bool, default: ``True``)
    Upload remaining files when pibooth exits.

``RCLONE_bulk_on_exit`` (bool, default: ``False``)
    Perform a single bulk ``rclone copy`` on exit.

``RCLONE_manifest_name`` (str, default: ``.rclone_uploaded_manifest.txt``)
    Manifest file used to track uploaded files.

``RCLONE_timeout_per_file`` (int, default: ``120``)
    Timeout (seconds) for each file upload.

``RCLONE_timeout_bulk`` (int, default: ``300``)
    Timeout (seconds) for bulk upload.

``RCLONE_include_qrcodes`` (bool, default: ``True``)
    Upload QR code images.

``RCLONE_qrcode_suffix`` (str, default: ``_qrcode``)
    Suffix used to identify QR code files.

``RCLONE_qrcode_ext`` (str, default: ``.png``)
    File extension for QR code images.

Upload Behaviour
----------------

During booth operation
~~~~~~~~~~~~~~~~~~~~~~

After each capture, the plugin:

- Scans the output folder
- Detects new files matching configured extensions
- Uploads them individually using ``rclone copyto``
- Records successful uploads in the manifest file

Uploads run in a background thread to avoid blocking the UI.

On exit
~~~~~~~

Two modes are available:

**1. Bulk mode** (``RCLONE_bulk_on_exit = True``)

.. code-block:: bash

    rclone copy <local_path>/ <remote>:<bucket>/<subdir>

**2. Per-file mode** (default)

Uploads any remaining files individually.

Manifest File
-------------

The manifest file:

- Prevents re-uploading files already sent
- Lives inside the local output folder
- Is appended to after each successful upload
- Is created automatically if missing

Deleting the manifest forces all files to be re-uploaded.

Dry Run Mode
------------

Enable:

.. code-block:: ini

    RCLONE_dry_run = True

This logs all upload commands without executing them.

Troubleshooting
---------------

**Uploads not happening**

- Ensure ``RCLONE_enabled = True``
- Confirm ``rclone`` is installed and in ``PATH``
- Verify the remote name using ``rclone listremotes``

**Files not being detected**

- Check ``RCLONE_file_extensions``
- Inspect the manifest file

**QR codes not uploading**

- Ensure ``RCLONE_include_qrcodes = True``
- Confirm suffix and extension match your QR generator

**Bulk upload fails**

- Increase ``RCLONE_timeout_bulk``
- Test manually:

.. code-block:: bash

    rclone copy <local> <remote>

Example Configuration
---------------------

.. code-block:: ini

    [RCLONE_UPLOAD]
    RCLONE_enabled = True
    RCLONE_remote = pibooth-cloudflare
    RCLONE_bucket = partyselfie
    RCLONE_subdir = event-2025
    RCLONE_local_path = Pictures
    RCLONE_rclone_args = --transfers=4 --checkers=8 --retries=3
    RCLONE_upload_on_exit = True
    RCLONE_bulk_on_exit = False
    RCLONE_include_qrcodes = True

Contributing
------------

Pull requests and feature suggestions are welcome.

License
-------

MIT License

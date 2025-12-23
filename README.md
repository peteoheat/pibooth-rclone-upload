# pibooth-rclone-upload
pibooth-rclone is a module for pibooth which uses the rclone commands to copy captured images from rclone to any of the storage solutions supported by rclone.
It can be used with many cloud storage providers such as AWS, Azure, Google or Cloudflare. Making it a storage agnostic solution.

# Configuration

    [RCLONE_UPLOAD]
    # <class 'bool'>
    # Required by 'rclone-upload' plugin
    RCLONE_enabled = True

    # <class 'str'>
    # Required by 'rclone-upload' plugin
    RCLONE_remote = myrclone-remotename

    # <class 'str'>
    # Required by 'rclone-upload' plugin
    RCLONE_bucket = mystoragebucket

    # <class 'str'>
    # Required by 'rclone-upload' plugin
    RCLONE_subdir = MYBUCKETSUBFOLDER

    # <class 'str'>
    # Required by 'rclone-upload' plugin
    RCLONE_local_path = /home/pi/Pictures

    # <class 'str'>
    # Required by 'rclone-upload' plugin
    RCLONE_rclone_args = --transfers=4 --checkers=8 --retries=3

    # <class 'bool'>
    # Required by 'rclone-upload' plugin
    RCLONE_dry_run = False

    # <class 'str'>
    # Required by 'rclone-upload' plugin
    RCLONE_file_extensions = .jpg,.jpeg,.png,.gif,.mp4,.json,.html

    # <class 'bool'>
    # Required by 'rclone-upload' plugin
    RCLONE_upload_on_exit = True

    # <class 'bool'>
    # Required by 'rclone-upload' plugin
    RCLONE_bulk_on_exit = False

    # <class 'str'>
    # Required by 'rclone-upload' plugin
    RCLONE_manifest_name = .rclone_uploaded_manifest.txt

    # <class 'int'>
    # Required by 'rclone-upload' plugin
    RCLONE_timeout_per_file = 120

    # <class 'int'>
    # Required by 'rclone-upload' plugin
    RCLONE_timeout_bulk = 300

    # <class 'bool'>
    # Required by 'rclone-upload' plugin
    RCLONE_include_qrcodes = True

    # <class 'str'>
    # Required by 'rclone-upload' plugin
    RCLONE_qrcode_suffix = _qrcode

    # <class 'str'>
    # Required by 'rclone-upload' plugin
    RCLONE_qrcode_ext = .png

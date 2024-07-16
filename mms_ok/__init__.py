import logging
import os
import shutil
import sys

from .utils import log

if os.name == "nt":  # Windows
    lib_dir = os.path.expanduser("~/mms_ok/")
    try:
        os.mkdir(lib_dir)
    except FileExistsError:
        pass

    frontpanel_dir = os.environ.get("okFP_ROOT", None)

    if frontpanel_dir is None:
        log("FrontPanel SDK seems not installed!", logging_level=logging.WARNING)

    try:
        with open(os.path.join(frontpanel_dir, "ReleaseNotes.txt"), "r") as f:
            line = f.readline().strip()
            _, version, *_ = line.split()
            log(f"FrontPanel SDK Version: {version}", logging_level=logging.INFO)

        files = [
            os.path.join(frontpanel_dir, "API/Python/x64/ok.py"),
            os.path.join(frontpanel_dir, "API/Python/x64/_ok.pyd"),
            os.path.join(frontpanel_dir, "API/lib/x64/okFrontPanel.dll"),
        ]

        for file in files:
            shutil.copy(src=file, dst=lib_dir)

        log("FrontPanel API ready", logging_level=logging.INFO)
    except FileNotFoundError:
        log("FrontPanel SDK files not found!", logging_level=logging.WARNING)
        log(f"Default Directory: {frontpanel_dir}", logging_level=logging.WARNING)

    sys.path.append(lib_dir)
else:
    log("OS is not Windows!", logging_level=logging.INFO)

try:
    import ok
except ImportError:
    log("Please manually setup FrontPanel SDK!", logging_level=logging.CRITICAL)
    raise ImportError("Import ok failed")

from .fpga import XEM7310, XEM7360

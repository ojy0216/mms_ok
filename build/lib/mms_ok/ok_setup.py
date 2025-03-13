import logging
import os
import shutil
import sys

from loog import log


def copy_frontpanel_files():
    if os.name == "nt":  # Windows
        lib_dir = os.path.expanduser("~/mms_ok/")
        try:
            os.mkdir(lib_dir)
        except FileExistsError:
            pass

        frontpanel_dir = os.environ.get("okFP_ROOT", None)

        if frontpanel_dir is None:
            frontpanel_dir = r"C:/Program Files/Opal Kelly/FrontPanelUSB/"

        if not os.path.exists(frontpanel_dir):
            log("FrontPanel SDK not found!", level="warning")
            log(f"Default Directory: {frontpanel_dir}", level="warning")
            return

        if not os.path.exists(frontpanel_dir):
            log("FrontPanel SDK not found!", level="warning")
            log(f"Default Directory: {frontpanel_dir}", level="warning")
            return

        try:
            with open(os.path.join(frontpanel_dir, "ReleaseNotes.txt"), "r") as f:
                line = f.readline().strip()
                _, version, *_ = line.split()
                log(f"FrontPanel SDK Version: {version}", level="info")

            files = [
                os.path.join(frontpanel_dir, "API/Python/x64/ok.py"),
                os.path.join(frontpanel_dir, "API/Python/x64/_ok.pyd"),
                os.path.join(frontpanel_dir, "API/lib/x64/okFrontPanel.dll"),
            ]

            for file in files:
                shutil.copy(src=file, dst=lib_dir)

            log("FrontPanel API ready", level="info")
        except FileNotFoundError:
            log("FrontPanel SDK files not found!", level="warning")
            log(f"Default Directory: {frontpanel_dir}", level="warning")

        sys.path.append(lib_dir)
    else:
        log("OS is not Windows!", logging_level=logging.INFO)

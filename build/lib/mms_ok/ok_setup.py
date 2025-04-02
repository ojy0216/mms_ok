import logging
import os
import shutil
import sys

from loguru import logger


def copy_frontpanel_files():
    if os.name == "nt":  # Windows
        lib_dir = os.path.expanduser("~/mms_ok/")
        try:
            os.mkdir(lib_dir)
        except FileExistsError:
            pass

        frontpanel_dir = r"C:\Program Files\Opal Kelly\FrontPanelUSB"

        if not os.path.exists(frontpanel_dir):
            logger.warning("FrontPanel SDK not found!")
            logger.warning(f"Default Directory: {frontpanel_dir}")
            return

        try:
            with open(os.path.join(frontpanel_dir, "ReleaseNotes.txt"), "r") as f:
                line = f.readline().strip()
                _, version, *_ = line.split()
                logger.info(f"FrontPanel SDK Version: {version}")

            files = [
                os.path.join(frontpanel_dir, "API/Python/x64/ok.py"),
                os.path.join(frontpanel_dir, "API/Python/x64/_ok.pyd"),
                os.path.join(frontpanel_dir, "API/lib/x64/okFrontPanel.dll"),
            ]

            for file in files:
                shutil.copy(src=file, dst=lib_dir)

            logger.info("FrontPanel API ready")
        except FileNotFoundError:
            logger.warning("FrontPanel SDK files not found!")
            logger.warning(f"Default Directory: {frontpanel_dir}")

        sys.path.append(lib_dir)
    else:
        logger.info("OS is not Windows!")

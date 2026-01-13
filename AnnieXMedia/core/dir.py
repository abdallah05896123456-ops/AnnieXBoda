# Authored By Certified Coders © 2025
import os
from ..logging import LOGGER

BASE_DIR = os.path.abspath(os.getcwd())

DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")
CACHE_DIR = os.path.join(BASE_DIR, "cache")
COUPLE_DIR = os.path.join(BASE_DIR, "couples")
BACKUP_DIR = os.path.join(BASE_DIR, "AnnieXMediaBackup")


def StorageManager():
    for path in (
        DOWNLOAD_DIR,
        CACHE_DIR,
        COUPLE_DIR,
        BACKUP_DIR,
    ):
        try:
            os.makedirs(path, exist_ok=True)
        except Exception as e:
            LOGGER(__name__).error(f"Failed creating dir {path}: {e}")

    LOGGER(__name__).info("Directories Updated.")

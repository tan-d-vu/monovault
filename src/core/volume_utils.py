"""Volume identification and discovery utilities for portable media support."""

import getpass
import logging
import os
import platform
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)


def generate_volume_id() -> str:
    """Generate a unique volume identifier.

    Returns:
        32-character hex string (UUID4)
    """
    return uuid.uuid4().hex


def read_volume_id(folder: Path) -> str | None:
    """Read volume_id from folder's .monovault sidecar.

    Args:
        folder: Path to folder containing .monovault directory

    Returns:
        Volume ID string if file exists and readable, None otherwise
    """
    volume_id_file = folder / ".monovault" / "volume_id"
    try:
        if volume_id_file.exists():
            return volume_id_file.read_text().strip()
    except OSError:
        pass
    return None


def write_volume_id(folder: Path) -> str:
    """Write a new volume_id to folder's .monovault sidecar.

    Args:
        folder: Path to folder where .monovault will be created

    Returns:
        The generated volume ID

    Raises:
        OSError: If .monovault directory creation or write fails
    """
    monovault_dir = folder / ".monovault"
    monovault_dir.mkdir(parents=True, exist_ok=True)
    volume_id = generate_volume_id()
    volume_id_file = monovault_dir / "volume_id"
    volume_id_file.write_text(volume_id)
    return volume_id


def ensure_volume_id(folder: Path) -> str | None:
    """Ensure volume_id exists, creating if necessary.

    Reads existing volume_id. If missing, generates and writes a new one.
    Handles read-only filesystems gracefully.

    Args:
        folder: Path to folder

    Returns:
        Volume ID string, or None if creation fails (logged as warning)
    """
    # Try reading existing volume_id first
    existing_id = read_volume_id(folder)
    if existing_id:
        return existing_id

    # Try creating new volume_id
    try:
        return write_volume_id(folder)
    except OSError as e:
        logger.warning(
            f"Cannot create volume_id in '{folder}': {e}. "
            "Portable re-association may not work for this folder."
        )
        return None


def get_mount_search_paths() -> list[Path]:
    """Get platform-specific mount points to search for volumes.

    Returns:
        List of Path objects to search for volume_id files

    Platform behavior:
        Linux: /run/media/<user>/*, /media/<user>/*, /mnt/*, /media/*
        macOS: /Volumes/*
        Windows: All existing drive letters A:\\ through Z:\\
    """
    system = platform.system()
    paths = []

    if system == "Linux":
        try:
            user = os.getlogin()
        except OSError:
            user = getpass.getuser()

        paths.extend(
            [
                Path(f"/run/media/{user}"),
                Path(f"/media/{user}"),
                Path("/mnt"),
                Path("/media"),
            ]
        )
    elif system == "Darwin":
        paths.append(Path("/Volumes"))
    elif system == "Windows":
        for drive_letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            drive = Path(f"{drive_letter}:\\")
            if drive.exists():
                paths.append(drive)

    return paths


def find_volume_by_id(volume_id: str) -> Path | None:
    """Find a volume by its volume_id.

    Searches all mount paths and subdirectories for a volume with matching
    volume_id file. Returns first match found.

    Args:
        volume_id: The volume ID to search for

    Returns:
        Path to volume root if found, None otherwise
    """
    search_paths = get_mount_search_paths()

    for mount_root in search_paths:
        if not mount_root.exists():
            continue

        try:
            # Check mount_root itself
            volume_id_file = mount_root / ".monovault" / "volume_id"
            if volume_id_file.exists():
                content = volume_id_file.read_text().strip()
                if content == volume_id:
                    return mount_root

            # Check immediate subdirectories
            for item in mount_root.iterdir():
                if not item.is_dir():
                    continue
                volume_id_file = item / ".monovault" / "volume_id"
                if volume_id_file.exists():
                    content = volume_id_file.read_text().strip()
                    if content == volume_id:
                        return item
        except OSError:
            # Skip inaccessible directories
            continue

    return None

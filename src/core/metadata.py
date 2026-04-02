from pathlib import Path
from typing import Optional
import mutagen
from mutagen.mp3 import MP3
from mutagen.flac import FLAC
from mutagen.wave import WAVE


SUPPORTED_EXTENSIONS = {".mp3", ".flac", ".wav"}


def is_supported(path: str) -> bool:
    return Path(path).suffix.lower() in SUPPORTED_EXTENSIONS


def read_metadata(file_path: str) -> dict:
    path = Path(file_path)
    if not path.exists():
        return {}

    try:
        audio = mutagen.File(file_path)
        if audio is None:
            return {}

        # FLAC specific handling
        if isinstance(audio, FLAC):
            if hasattr(audio, "pictures") and audio.pictures:
                metadata = {
                    "title": audio.get("title", [""])[0] if audio.get("title") else "",
                    "artist": audio.get("artist", [""])[0]
                    if audio.get("artist")
                    else "",
                    "album": audio.get("album", [""])[0] if audio.get("album") else "",
                    "duration": getattr(audio.info, "length", 0.0),
                    "album_art": audio.pictures[0].data if audio.pictures else None,
                }
                return metadata

        metadata = {
            "title": "",
            "artist": "",
            "album": "",
            "duration": 0.0,
            "album_art": None,
        }

        if hasattr(audio, "tags") and audio.tags:
            metadata["title"] = (
                str(audio.tags.get("title", [""])[0]) if audio.tags.get("title") else ""
            )
            metadata["artist"] = (
                str(audio.tags.get("artist", [""])[0])
                if audio.tags.get("artist")
                else ""
            )
            metadata["album"] = (
                str(audio.tags.get("album", [""])[0]) if audio.tags.get("album") else ""
            )

            # FLAC uses PICTURE
            if hasattr(audio.tags, "getall"):
                all_pics_flac = list(audio.tags.getall("PICTURE"))
                if all_pics_flac:
                    metadata["album_art"] = all_pics_flac[0].data
                else:
                    all_pics = list(audio.tags.getall("APIC"))
                    if all_pics:
                        metadata["album_art"] = all_pics[0].data
                    else:
                        all_covr = list(audio.tags.getall("covr"))
                        if all_covr:
                            metadata["album_art"] = all_covr[0].data

        if audio.info:
            metadata["duration"] = getattr(audio.info, "length", 0.0)

        return metadata
    except Exception:
        return {}


def read_comment(file_path: str) -> list[str]:
    path = Path(file_path)
    if not path.exists():
        return []

    try:
        audio = mutagen.File(file_path)
        if audio is None or not hasattr(audio, "tags") or audio.tags is None:
            return []

        comment = audio.tags.get("COMMENT")
        if comment:
            return comment[0].split() if comment[0] else []

        comment = audio.tags.get("COMM")
        if comment:
            return comment[0].text.split() if comment[0].text else []

        return []
    except Exception:
        return []


def write_comment(file_path: str, categories: list[str]) -> bool:
    path = Path(file_path)
    if not path.exists():
        return False

    try:
        audio = mutagen.File(file_path)
        if audio is None:
            return False

        comment_text = " ".join(categories)

        if isinstance(audio, MP3):
            audio.tags["COMM"] = mutagen.id3.COMM(
                encoding=3,
                lang="eng",
                text=comment_text,
            )
        elif isinstance(audio, FLAC):
            audio.tags["COMMENT"] = [comment_text]
        elif isinstance(audio, WAVE):
            audio.tags["COMM"] = [comment_text]

        audio.save()
        return True
    except Exception:
        return False


def get_album_art(file_path: str) -> Optional[bytes]:
    try:
        audio = mutagen.File(file_path)
        if audio is None or not hasattr(audio, "tags") or audio.tags is None:
            return None

        if hasattr(audio.tags, "getall"):
            for pic in audio.tags.getall("APIC"):
                return pic.data
            for pic in audio.tags.getall("covr"):
                return pic.data

        return None
    except Exception:
        return None

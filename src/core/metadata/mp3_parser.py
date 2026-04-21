"""MP3 metadata parser using ID3 tags."""

import logging
from pathlib import Path

import mutagen
import mutagen.id3

from .base import BaseParser

logger = logging.getLogger(__name__)


class Mp3Parser(BaseParser):
    supported_extensions: set[str] = {".mp3"}

    def read_metadata(self, file_path: str) -> dict:
        path = Path(file_path)
        if not path.exists():
            return {}

        try:
            audio = mutagen.File(file_path)
            if audio is None:
                return {}

            metadata: dict = {
                "title": "",
                "artist": "",
                "album": "",
                "duration": 0.0,
                "album_art": None,
            }

            if hasattr(audio, "tags") and audio.tags:
                try:
                    metadata["title"] = (
                        str(audio.tags.get("title", [""])[0]) if audio.tags.get("title") else ""
                    )
                except (IndexError, TypeError, AttributeError) as e:
                    logger.error("Error reading title tag for %s: %s", file_path, e)

                try:
                    metadata["artist"] = (
                        str(audio.tags.get("artist", [""])[0]) if audio.tags.get("artist") else ""
                    )
                except (IndexError, TypeError, AttributeError) as e:
                    logger.error("Error reading artist tag for %s: %s", file_path, e)

                try:
                    metadata["album"] = (
                        str(audio.tags.get("album", [""])[0]) if audio.tags.get("album") else ""
                    )
                except (IndexError, TypeError, AttributeError) as e:
                    logger.error("Error reading album tag for %s: %s", file_path, e)

                if hasattr(audio.tags, "getall"):
                    try:
                        all_pics = list(audio.tags.getall("APIC"))
                        if all_pics:
                            metadata["album_art"] = all_pics[0].data
                        else:
                            all_covr = list(audio.tags.getall("covr"))
                            if all_covr:
                                metadata["album_art"] = all_covr[0].data
                    except (AttributeError, IndexError) as e:
                        logger.error("Error reading album art for %s: %s", file_path, e)

            if audio.info:
                metadata["duration"] = getattr(audio.info, "length", 0.0)

            return metadata
        except mutagen.MutagenError as e:
            logger.error("Failed to read metadata for %s: %s", file_path, e)
            return {}

    def read_comment(self, file_path: str) -> list[str]:
        path = Path(file_path)
        if not path.exists():
            return []

        try:
            audio = mutagen.File(file_path)
            if audio is None:
                return []

            if not hasattr(audio, "tags") or audio.tags is None:
                return []

            if hasattr(audio.tags, "getall"):
                comm_all = list(audio.tags.getall("COMM"))
                if comm_all:
                    try:
                        text = comm_all[0].text
                        if isinstance(text, list) and text:
                            text = text[0]
                        if text:
                            return text.split()
                    except (IndexError, AttributeError, TypeError) as e:
                        logger.error("Error parsing COMM tag for %s: %s", file_path, e)
                    return []

            return []
        except mutagen.MutagenError as e:
            logger.error("Failed to read comment for %s: %s", file_path, e)
            return []

    def read_comment_raw(self, file_path: str) -> str:
        path = Path(file_path)
        if not path.exists():
            return ""

        try:
            audio = mutagen.File(file_path)
            if audio is None:
                return ""

            if not hasattr(audio, "tags") or audio.tags is None:
                return ""

            if hasattr(audio.tags, "getall"):
                comm_all = list(audio.tags.getall("COMM"))
                if comm_all:
                    try:
                        text = comm_all[0].text
                        if isinstance(text, list) and text:
                            text = text[0]
                        if text:
                            return text
                    except (IndexError, AttributeError, TypeError) as e:
                        logger.error("Error parsing COMM tag (raw) for %s: %s", file_path, e)

            return ""
        except mutagen.MutagenError as e:
            logger.error("Failed to read raw comment for %s: %s", file_path, e)
            return ""

    def write_comment(self, file_path: str, categories: list[str]) -> bool:
        path = Path(file_path)
        if not path.exists():
            return False

        try:
            audio = mutagen.File(file_path)
            if audio is None:
                return False

            comment_text = " ".join(categories)

            if audio.tags is None:
                audio.add_tags()
            audio.tags.setall(
                "COMM",
                [
                    mutagen.id3.COMM(
                        encoding=3,
                        lang="eng",
                        text=comment_text,
                    )
                ],
            )
            audio.save()
            return True
        except mutagen.MutagenError as e:
            logger.error("Failed to write comment for %s: %s", file_path, e)
            return False
        except AttributeError as e:
            logger.error("Attribute error writing comment for %s: %s", file_path, e)
            return False

    def write_comments(self, file_path: str, comments: str) -> bool:
        path = Path(file_path)
        if not path.exists():
            return False

        try:
            audio = mutagen.File(file_path)
            if audio is None:
                return False

            if audio.tags is None:
                audio.add_tags()
            audio.tags.setall(
                "COMM",
                [
                    mutagen.id3.COMM(
                        encoding=3,
                        lang="eng",
                        text=comments,
                    )
                ],
            )
            audio.save()
            return True
        except mutagen.MutagenError as e:
            logger.error("Failed to write comments for %s: %s", file_path, e)
            return False
        except AttributeError as e:
            logger.error("Attribute error writing comments for %s: %s", file_path, e)
            return False

    def get_album_art(self, file_path: str) -> bytes | None:
        try:
            audio = mutagen.File(file_path)
            if audio is None or not hasattr(audio, "tags") or audio.tags is None:
                return None

            if hasattr(audio.tags, "getall"):
                try:
                    for pic in audio.tags.getall("APIC"):
                        return pic.data
                    for pic in audio.tags.getall("covr"):
                        return pic.data
                except (AttributeError, IndexError) as e:
                    logger.error("Error reading album art for %s: %s", file_path, e)

            return None
        except mutagen.MutagenError as e:
            logger.error("Failed to get album art for %s: %s", file_path, e)
            return None

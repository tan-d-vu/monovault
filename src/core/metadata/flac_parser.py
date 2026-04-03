"""FLAC metadata parser using Vorbis comment tags."""
import logging
from pathlib import Path
from typing import Optional
import mutagen
from mutagen.flac import FLAC
from .base import BaseParser

logger = logging.getLogger(__name__)


class FlacParser(BaseParser):
    supported_extensions: set[str] = {".flac"}

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

            if isinstance(audio, FLAC):
                try:
                    metadata["title"] = (
                        audio.get("title", [""])[0] if audio.get("title") else ""
                    )
                except (IndexError, TypeError, AttributeError) as e:
                    logger.error("Error reading title tag for %s: %s", file_path, e)

                try:
                    metadata["artist"] = (
                        audio.get("artist", [""])[0] if audio.get("artist") else ""
                    )
                except (IndexError, TypeError, AttributeError) as e:
                    logger.error("Error reading artist tag for %s: %s", file_path, e)

                try:
                    metadata["album"] = (
                        audio.get("album", [""])[0] if audio.get("album") else ""
                    )
                except (IndexError, TypeError, AttributeError) as e:
                    logger.error("Error reading album tag for %s: %s", file_path, e)

                try:
                    if hasattr(audio, "pictures") and audio.pictures:
                        metadata["album_art"] = audio.pictures[0].data
                except (IndexError, AttributeError) as e:
                    logger.error("Error reading pictures for %s: %s", file_path, e)

                metadata["duration"] = getattr(audio.info, "length", 0.0)
                return metadata

            # Fallback for FLAC loaded via generic mutagen path
            if hasattr(audio, "tags") and audio.tags:
                try:
                    metadata["title"] = (
                        str(audio.tags.get("title", [""])[0])
                        if audio.tags.get("title")
                        else ""
                    )
                except (IndexError, TypeError, AttributeError) as e:
                    logger.error("Error reading title tag for %s: %s", file_path, e)

                try:
                    metadata["artist"] = (
                        str(audio.tags.get("artist", [""])[0])
                        if audio.tags.get("artist")
                        else ""
                    )
                except (IndexError, TypeError, AttributeError) as e:
                    logger.error("Error reading artist tag for %s: %s", file_path, e)

                try:
                    metadata["album"] = (
                        str(audio.tags.get("album", [""])[0])
                        if audio.tags.get("album")
                        else ""
                    )
                except (IndexError, TypeError, AttributeError) as e:
                    logger.error("Error reading album tag for %s: %s", file_path, e)

                if hasattr(audio.tags, "getall"):
                    try:
                        all_pics_flac = list(audio.tags.getall("PICTURE"))
                        if all_pics_flac:
                            metadata["album_art"] = all_pics_flac[0].data
                    except (AttributeError, IndexError) as e:
                        logger.error(
                            "Error reading album art for %s: %s", file_path, e
                        )

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

            comment = audio.tags.get("COMMENT")
            if comment:
                try:
                    text = comment[0] if isinstance(comment, list) else comment
                    if isinstance(text, list) and text:
                        text = text[0]
                    if text:
                        return text.split()
                except (IndexError, TypeError, AttributeError) as e:
                    logger.error(
                        "Error parsing COMMENT tag for %s: %s", file_path, e
                    )
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

            comment = audio.tags.get("COMMENT")
            if comment:
                try:
                    text = comment[0] if isinstance(comment, list) else comment
                    if isinstance(text, list) and text:
                        text = text[0]
                    if text:
                        return text
                except (IndexError, TypeError, AttributeError) as e:
                    logger.error(
                        "Error parsing COMMENT tag (raw) for %s: %s", file_path, e
                    )

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
            audio.tags["COMMENT"] = [comment_text]
            audio.save()
            return True
        except mutagen.MutagenError as e:
            logger.error("Failed to write comment for %s: %s", file_path, e)
            return False
        except (AttributeError, TypeError) as e:
            logger.error("Error writing comment for %s: %s", file_path, e)
            return False

    def write_comments(self, file_path: str, comments: str) -> bool:
        path = Path(file_path)
        if not path.exists():
            return False

        try:
            audio = mutagen.File(file_path)
            if audio is None:
                return False

            audio.tags["COMMENT"] = [comments]
            audio.save()
            return True
        except mutagen.MutagenError as e:
            logger.error("Failed to write comments for %s: %s", file_path, e)
            return False
        except (AttributeError, TypeError) as e:
            logger.error("Error writing comments for %s: %s", file_path, e)
            return False

    def get_album_art(self, file_path: str) -> Optional[bytes]:
        try:
            audio = mutagen.File(file_path)
            if audio is None:
                return None

            if isinstance(audio, FLAC):
                try:
                    if hasattr(audio, "pictures") and audio.pictures:
                        return audio.pictures[0].data
                except (AttributeError, IndexError) as e:
                    logger.error("Error reading pictures for %s: %s", file_path, e)
                return None

            if not hasattr(audio, "tags") or audio.tags is None:
                return None

            if hasattr(audio.tags, "getall"):
                try:
                    all_pics_flac = list(audio.tags.getall("PICTURE"))
                    if all_pics_flac:
                        return all_pics_flac[0].data
                except (AttributeError, IndexError) as e:
                    logger.error("Error reading album art for %s: %s", file_path, e)

            return None
        except mutagen.MutagenError as e:
            logger.error("Failed to get album art for %s: %s", file_path, e)
            return None

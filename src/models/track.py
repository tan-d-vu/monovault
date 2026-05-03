from dataclasses import dataclass
from pathlib import Path


@dataclass
class Track:
    id: int
    file_path: str
    title: str
    artist: str
    album: str
    duration: float
    categories: list[str]
    album_art: bytes | None
    folder_path: str
    comments: str = ""
    date_added: str = ""
    bpm: float | None = None

    @property
    def filename(self) -> str:
        return Path(self.file_path).name

    @property
    def location(self) -> str:
        if not self.file_path:
            return ""
        return str(Path(self.file_path).parent)

    @property
    def duration_formatted(self) -> str:
        mins, secs = divmod(int(self.duration), 60)
        return f"{mins:02d}:{secs:02d}"

    @property
    def categories_str(self) -> str:
        return " ".join(self.categories)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "file_path": self.file_path,
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "duration": self.duration,
            "categories": " ".join(self.categories),
            "folder_path": self.folder_path,
        }

    @classmethod
    def from_dict(cls, data: dict, album_art: bytes | None = None) -> "Track":
        categories = data.get("categories", "").split() if data.get("categories") else []
        return cls(
            id=data["id"],
            file_path=data["file_path"],
            title=data.get("title", "Unknown"),
            artist=data.get("artist", "Unknown"),
            album=data.get("album", "Unknown"),
            duration=data.get("duration", 0.0),
            categories=categories,
            album_art=album_art,
            folder_path=data.get("folder_path", ""),
        )

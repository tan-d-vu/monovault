"""Date preset filter for track lists."""

from datetime import date, timedelta
from enum import Enum

from ..models.track import Track


class DatePreset(Enum):
    LAST_7_DAYS = "Last 7 days"
    LAST_30_DAYS = "Last 30 days"
    LAST_3_MONTHS = "Last 3 months"
    THIS_YEAR = "This year"


def cutoff_date(preset: DatePreset) -> date:
    today = date.today()
    if preset == DatePreset.LAST_7_DAYS:
        return today - timedelta(days=7)
    if preset == DatePreset.LAST_30_DAYS:
        return today - timedelta(days=30)
    if preset == DatePreset.LAST_3_MONTHS:
        return today - timedelta(days=90)
    return date(today.year, 1, 1)  # THIS_YEAR


def apply_date_filter(tracks: list[Track], preset: DatePreset | None) -> list[Track]:
    if preset is None:
        return tracks
    cutoff = cutoff_date(preset).isoformat()
    return [t for t in tracks if t.date_added >= cutoff]

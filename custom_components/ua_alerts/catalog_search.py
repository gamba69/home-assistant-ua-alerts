"""Pure search helpers for the UA Alerts territory catalog."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from .models import LocationDefinition

# Historical / common-language aliases which cannot be derived reliably from the
# current official administrative title. Values are official alerts.in.ua UIDs.
_UID_ALIASES: dict[str, tuple[str, ...]] = {
    "31": ("Київ", "Киев", "город Киев", "місто Київ"),
    "14": ("Киевская область", "Киевская обл", "Київщина"),
    "726": (
        "Кагарлик",
        "Кагарлык",
        "Кагарлицький район",
        "Кагарлыкский район",
        "Кагарлицька громада",
    ),
    "38": ("Володимир-Волинський район", "Владимир-Волынский район"),
    "255": ("Володимир-Волинська громада", "Владимир-Волынский"),
    "43": ("Новомосковський район", "Новомосковский район"),
    "327": ("Новомосковськ", "Новомосковск", "Новомосковська громада"),
    "60": ("Новоград-Волинський район", "Новоград-Волынский район"),
    "471": ("Новоград-Волинський", "Новоград-Волынский", "Новоград-Волинська громада"),
    "84": ("Сєвєродонецький район", "Северодонецкий район"),
    "820": ("Сєвєродонецьк", "Северодонецк", "Сєвєродонецька громада"),
    "92": ("Червоноградський район", "Червоноградский район"),
    "832": ("Червоноград", "Червоноградська громада"),
    "127": ("Красноградський район", "Красноградский район"),
    "1324": ("Красноград", "Красноградська громада"),
}

_APOSTROPHES = str.maketrans({"’": "'", "ʼ": "'", "`": "'", "´": "'", "‘": "'"})
_SEARCH_TRANSLATION = str.maketrans({"ё": "е", "і": "и", "ї": "и", "є": "е", "ґ": "г"})
_NON_WORD = re.compile(r"[^0-9a-zа-я' ]+", re.IGNORECASE)
_SPACES = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class CatalogSearchResult:
    """One ranked territory-search result."""

    location: LocationDefinition
    label: str
    score: tuple[int, int, str]


def normalize_search_text(value: str) -> str:
    """Normalize Ukrainian/Russian user text for forgiving catalog lookup."""
    value = unicodedata.normalize("NFKC", value).casefold().translate(_APOSTROPHES)
    value = value.translate(_SEARCH_TRANSLATION)
    value = value.replace("-", " ")
    value = _NON_WORD.sub(" ", value)
    return _SPACES.sub(" ", value).strip()


def location_path_label(location: LocationDefinition) -> str:
    """Return an unambiguous human-readable label for a location."""
    if location.location_type == "hromada":
        parents = " / ".join(
            part for part in (location.oblast_title, location.raion_title) if part
        )
        return f"{location.location_title} — {parents}" if parents else location.location_title
    if location.location_type == "raion" and location.oblast_title:
        return f"{location.location_title} — {location.oblast_title}"
    return location.location_title


def _search_strings(location: LocationDefinition) -> tuple[str, ...]:
    path = " ".join(
        part
        for part in (
            location.location_title,
            location.oblast_title,
            location.raion_title,
            location.location_uid,
        )
        if part
    )
    values = [location.location_title, path, location.location_uid]
    values.extend(_UID_ALIASES.get(location.location_uid, ()))
    return tuple(normalize_search_text(value) for value in values if value)


def search_catalog(
    catalog: tuple[LocationDefinition, ...],
    query: str,
    *,
    limit: int = 50,
) -> tuple[CatalogSearchResult, ...]:
    """Search the complete catalog, ranking exact/title matches first."""
    needle = normalize_search_text(query)
    if not needle:
        return ()
    tokens = tuple(token for token in needle.split(" ") if token)
    results: list[CatalogSearchResult] = []

    for location in catalog:
        haystacks = _search_strings(location)
        title = normalize_search_text(location.location_title)
        alias_values = tuple(normalize_search_text(v) for v in _UID_ALIASES.get(location.location_uid, ()))

        if needle == location.location_uid:
            rank = 0
        elif needle == title or needle in alias_values:
            rank = 1
        elif title.startswith(needle) or any(alias.startswith(needle) for alias in alias_values):
            rank = 2
        elif needle in title or any(needle in alias for alias in alias_values):
            rank = 3
        elif any(needle in haystack for haystack in haystacks):
            rank = 4
        elif tokens and all(any(token in haystack for haystack in haystacks) for token in tokens):
            rank = 5
        else:
            continue

        label = location_path_label(location)
        results.append(
            CatalogSearchResult(
                location=location,
                label=label,
                score=(rank, len(title), label.casefold()),
            )
        )

    results.sort(key=lambda item: item.score)
    return tuple(results[: max(1, limit)])

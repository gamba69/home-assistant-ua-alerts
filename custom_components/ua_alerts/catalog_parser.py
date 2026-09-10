"""Pure parser for the alerts.in.ua location catalog."""

from __future__ import annotations

import csv
import io

from .models import LocationDefinition

_TYPE_MAP = {
    "область": "oblast",
    "район": "raion",
    "громада": "hromada",
    "місто з спеціальним статусом": "city",
    "місто зі спеціальним статусом": "city",
}


def parse_catalog_csv(
    text: str,
    *,
    validate_full: bool = True,
) -> tuple[LocationDefinition, ...]:
    """Parse the official alerts.in.ua location spreadsheet CSV."""
    rows = list(csv.reader(io.StringIO(text)))
    result: list[LocationDefinition] = []
    seen: set[str] = set()
    current_oblast: tuple[str, str] | None = None
    current_raion: tuple[str, str] | None = None

    for row in rows:
        if len(row) < 3:
            continue
        uid = row[0].strip()
        title = row[1].strip()
        location_type = _TYPE_MAP.get(row[2].strip().casefold())
        if not uid.isdigit() or not title or location_type is None or uid in seen:
            continue

        seen.add(uid)
        if location_type == "city":
            result.append(LocationDefinition(uid, title, "city"))
            continue

        if location_type == "oblast":
            result.append(LocationDefinition(uid, title, "oblast"))
            # AR Crimea is standalone in the official sheet and currently sits
            # between the Volyn oblast row and Volyn's first raion. It must not
            # replace the active parent block.
            if uid != "29":
                current_oblast = (uid, title)
                current_raion = None
            continue

        if location_type == "raion":
            if current_oblast is None:
                continue
            current_raion = (uid, title)
            result.append(
                LocationDefinition(
                    uid,
                    title,
                    "raion",
                    oblast_uid=current_oblast[0],
                    oblast_title=current_oblast[1],
                )
            )
            continue

        if current_oblast is None or current_raion is None:
            continue
        result.append(
            LocationDefinition(
                uid,
                title,
                "hromada",
                oblast_uid=current_oblast[0],
                oblast_title=current_oblast[1],
                raion_uid=current_raion[0],
                raion_title=current_raion[1],
            )
        )

    locations = tuple(result)
    if validate_full:
        validate_full_catalog(locations)
    return locations


def validate_full_catalog(locations: tuple[LocationDefinition, ...]) -> None:
    """Reject a partial or structurally mis-grouped remote catalog."""
    by_uid = {item.location_uid: item for item in locations}
    if len(by_uid) < 1500:
        raise ValueError(f"location catalog is unexpectedly small: {len(by_uid)}")
    if not {"31", "14", "75", "76", "699", "726", "1611"}.issubset(by_uid):
        raise ValueError("location catalog is missing required anchor UIDs")
    if by_uid["31"].location_type != "city":
        raise ValueError("Kyiv UID 31 is not a city")
    if by_uid["75"].oblast_uid != "14":
        raise ValueError("Buchanskyi raion is not grouped under Kyiv oblast")
    if by_uid["699"].raion_uid != "75" or by_uid["699"].oblast_uid != "14":
        raise ValueError("Bilohorodska hromada hierarchy is invalid")
    if by_uid["726"].raion_uid != "76" or by_uid["726"].oblast_uid != "14":
        raise ValueError("Kaharlytska hromada hierarchy is invalid")
    if by_uid["726"].location_title != "Кагарлицька територіальна громада":
        raise ValueError("Kaharlytska hromada title is invalid")


def catalog_is_full(locations: tuple[LocationDefinition, ...]) -> bool:
    return len(locations) >= 1500 and any(
        item.location_type == "hromada" and item.raion_uid for item in locations
    )

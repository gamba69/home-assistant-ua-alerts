#!/usr/bin/env python3
"""Refresh the bundled alerts.in.ua location snapshot for a release.

This is a release-maintainer tool only. The integration never runs it itself.
Runtime catalog refresh remains an explicit user action in Home Assistant.
"""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import sys
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from custom_components.ua_alerts.catalog_parser import parse_catalog_csv  # noqa: E402
from custom_components.ua_alerts.const import CATALOG_URL  # noqa: E402

DESTINATION = ROOT / "custom_components" / "ua_alerts" / "locations.json"


def main() -> None:
    request = Request(CATALOG_URL, headers={"User-Agent": "UA-Alerts-catalog-builder/1"})
    with urlopen(request, timeout=30) as response:  # noqa: S310 - fixed HTTPS URL
        text = response.read().decode("utf-8-sig")
    locations = parse_catalog_csv(text, validate_full=True)
    DESTINATION.write_text(
        json.dumps([asdict(item) for item in locations], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(locations)} validated locations to {DESTINATION}")


if __name__ == "__main__":
    main()

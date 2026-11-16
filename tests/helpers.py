"""Shared helpers: scenarios replayed by the heat pump simulator and platform rules."""
from __future__ import annotations

import json
from pathlib import Path

from .mock_pac import load_dump

FIXTURES = Path(__file__).parent / "fixtures"
BASELINE = json.loads((FIXTURES / "baseline_2.4.3.json").read_text(encoding="utf8"))

# IDs handled by the climate / water heater entities (see const.py)
EXCLUDED_IDS = {
    "hc_desired_day_temp", "hc_desired_night_temp", "hc_turned_on", "timer_programme",
    "wh_turned_on", "wh_desired_temp", "hc_name",
}


def scenarios() -> dict[str, dict[str, str]]:
    """Real field dumps (from the upstream repository) and variants of them."""
    duo = load_dump(FIXTURES / "field_dump_duo.txt")
    mono = load_dump(FIXTURES / "field_dump_mono.txt")
    no_room_sensor = dict(duo)
    no_room_sensor["2_Temp_Prostora"] = "-9999"
    return {"duo": duo, "mono": mono, "no_room_sensor": no_room_sensor}


def platform_of(cfg) -> str:
    """Platform that creates an entity for a tag configuration."""
    if cfg.id in EXCLUDED_IDS:
        return "excluded"
    if cfg.type == "boolean":
        return "switch" if cfg.adjustable.enabled else "binary_sensor"
    if cfg.type in ("float", "integer"):
        return "number" if cfg.adjustable.enabled else "sensor"
    return "select" if cfg.adjustable.enabled else "sensor"


def api_snapshot(values) -> dict[str, dict]:
    """Comparable view of what the API client returned."""
    return {
        v.config.unique_id: {
            "tag": v.tag,
            "value": v.value,
            "type": v.config.type,
            "name_en": v.config.name.en,
            "name_si": v.config.name.si,
            "unit": getattr(v.config, "unit", None),
            "adjustable": v.config.adjustable.model_dump(),
            "platform": platform_of(v.config),
        }
        for v in values
    }

"""Static checks of config.yml."""
from pathlib import Path

import yaml
from pydantic import TypeAdapter

from custom_components.orca.models import OrcaTagConfig

CONFIG = yaml.safe_load(
    (Path(__file__).parents[1] / "custom_components/orca/config.yml").read_text(encoding="utf8")
)


def test_schema_is_valid():
    TypeAdapter(list[OrcaTagConfig]).validate_python(CONFIG)


def test_tags_are_unique():
    tags = [c["tag"] for c in CONFIG]
    assert len(tags) == len(set(tags))


def test_id_and_circuit_pairs_are_unique():
    keys = [(c["id"], c["heating_circuit"]) for c in CONFIG]
    assert len(keys) == len(set(keys))


def test_numeric_settings_have_a_usable_range():
    for c in CONFIG:
        if c["type"] in ("float", "integer") and c["adjustable"]["enabled"]:
            r = c["adjustable"]["range"]
            assert r["min"] < r["max"] and r["step"] > 0, c["tag"]


def test_alarms_and_measurements_are_read_only():
    for c in CONFIG:
        if c["id"].startswith(("alarm_", "error_code", "hp_power", "power_limit_", "compressor_hours", "heater_hours")):
            assert not c["adjustable"]["enabled"], c["tag"]


def test_dashboard_example_is_valid():
    """The example dashboard parses and only uses built-in cards."""
    dashboard = yaml.safe_load(
        (Path(__file__).parents[1] / "dashboards/pompe-a-chaleur.yaml").read_text(encoding="utf8")
    )
    cards = [c for v in dashboard["views"] for s in v["sections"] for c in s["cards"]]
    assert {v["path"] for v in dashboard["views"]} == {"accueil", "technique", "reglages", "programmes"}
    assert cards and all(not c["type"].startswith("custom:") for c in cards)
    assert all("entity" in c for c in cards if c["type"] == "tile")

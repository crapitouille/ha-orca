"""Every setting exposed by the integration can be changed from the example dashboards.

The integration is set up against the heat pump simulator as on the reference
installation (floor heating circuit "Floor" and domestic hot water). Each adjustable
entity it creates must be editable in dashboards/pompe-a-chaleur.yaml, and every helper
of the house scenarios package in examples/scenarios-eau-chaude-cartes.yaml.
"""
from pathlib import Path

import yaml
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .helpers import scenarios

ROOT = Path(__file__).parents[1]
DASHBOARD = yaml.safe_load((ROOT / "dashboards/pompe-a-chaleur.yaml").read_text(encoding="utf8"))
SCENARIO_CARDS = yaml.safe_load((ROOT / "examples/scenarios-eau-chaude-cartes.yaml").read_text(encoding="utf8"))
PACKAGE = yaml.safe_load((ROOT / "examples/scenarios-eau-chaude.yaml").read_text(encoding="utf8"))

ADJUSTABLE_DOMAINS = ("number", "switch", "climate", "water_heater")
TILE_CONTROLS = {"numeric-input", "toggle", "target-temperature", "climate-hvac-modes", "select-options"}
PREFIX = "orca_heat_pump_"   # device name prefix, added by Home Assistant 2026.10 and later


def normalize(entity_id: str) -> str:
    domain, object_id = entity_id.split(".", 1)
    return f"{domain}.{object_id.removeprefix(PREFIX)}"


def _cards(node):
    """Every card of a dashboard, a view list or a card list, nested ones included."""
    if isinstance(node, dict):
        if "type" in node and node.get("type") not in ("buttons", "divider", "section", "grid"):
            yield node
        for key in ("views", "sections", "cards", "card"):
            if key in node:
                yield from _cards(node[key])
    elif isinstance(node, list):
        for item in node:
            yield from _cards(item)


def references(cards):
    """Entities shown anywhere in the cards."""
    found = set()

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "entity" and isinstance(value, str):
                    found.add(value)
                elif key == "entities" and isinstance(value, list):
                    found.update(v for v in value if isinstance(v, str))
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(cards)
    return found


def editable(cards):
    """Entities that can be changed from the cards, not only displayed."""
    found = set()
    for card in _cards(cards):
        if card["type"] == "tile" and {f["type"] for f in card.get("features", [])} & TILE_CONTROLS:
            found.add(card["entity"])
        if card["type"] == "entities":
            for row in card["entities"]:
                row = {"entity": row} if isinstance(row, str) else row
                if "entity" in row:   # number, switch, input_* rows are controls
                    found.add(row["entity"])
                for button in row.get("entities", []) if row.get("type") == "buttons" else []:
                    if button.get("tap_action", {}).get("action") == "toggle":
                        found.add(button["entity"])
    return found


async def _reference_installation(hass, pac_factory):
    values = scenarios()["duo"]
    values["MK1_IME"] = "11"           # circuit 1 named "Floor"
    pac, host = await pac_factory(values)
    entry = MockConfigEntry(
        domain="orca", title=host, unique_id=host,
        data={"hostname": host, "username": "admin", "password": "admin", "language": "English",
              "circuits": [1, 4]},     # floor heating and hot water only
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return {normalize(e.entity_id): e for e in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)}


async def test_every_heat_pump_setting_is_editable(hass, pac_factory):
    entities = await _reference_installation(hass, pac_factory)
    adjustable = {eid for eid, e in entities.items() if e.domain in ADJUSTABLE_DOMAINS}
    assert len(adjustable) > 150

    shown = {normalize(e) for e in editable(DASHBOARD)}
    assert sorted(adjustable - shown) == []


async def test_dashboard_entities_exist(hass, pac_factory):
    entities = await _reference_installation(hass, pac_factory)
    orca = {normalize(e) for e in references(DASHBOARD) if e.split(".", 1)[1].startswith(PREFIX)}
    assert sorted(orca - set(entities)) == []


def test_every_scenario_setting_is_editable():
    helpers = {
        f"{domain}.{name}"
        for domain in ("input_select", "input_number", "input_boolean")
        for name in PACKAGE[domain]
    }
    # a sensor choice is stored in an input_text and changed with the select of the same name
    helpers |= {f"select.{name}" for name in PACKAGE["input_text"]}
    assert sorted(helpers - editable(SCENARIO_CARDS)) == []
    # the anti-legionella programme driven by the package can be changed there too
    assert {
        "switch.orca_heat_pump_legionella_programme", "number.orca_heat_pump_legionella_temperature",
        "number.orca_heat_pump_legionella_start_day", "number.orca_heat_pump_legionella_start_hour",
        "number.orca_heat_pump_legionella_start_minute",
    } <= editable(SCENARIO_CARDS)
    # every entity of the cards is created by the package or by the integration
    package = helpers | {f"timer.{n}" for n in PACKAGE["timer"]} | {
        e.get("default_entity_id", "sensor.injection_reseau")
        for block in PACKAGE["template"] for entities in block.values() for e in entities
    }
    assert all(e in package or e.split(".", 1)[1].startswith(PREFIX) for e in references(SCENARIO_CARDS))


def test_dashboard_only_uses_built_in_cards():
    for cards in (DASHBOARD, SCENARIO_CARDS):
        assert all(not c["type"].startswith("custom:") for c in _cards(cards))

"""Integration tests inside a real Home Assistant instance (in memory).

The integration is set up against the heat pump simulator; the original entities
must match upstream 2.4.3 (tests/fixtures/baseline_2.4.3.json).
"""
import logging

import pytest
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .helpers import BASELINE, scenarios

SCENARIOS = ["duo", "mono", "no_room_sensor"]


async def _setup(hass, pac_factory, values):
    pac, host = await pac_factory(values)
    entry = MockConfigEntry(
        domain="orca", title=host, unique_id=host,
        data={"hostname": host, "username": "admin", "password": "admin", "language": "English"},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return pac, entry


def _inventory(hass, entry):
    """Entities of the config entry, keyed by the unique ID defined in config.yml."""
    inventory = {}
    for e in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id):
        state = hass.states.get(e.entity_id)
        inventory[e.unique_id.replace(entry.entry_id + "_", "", 1)] = {
            "entity_id": e.entity_id,
            "domain": e.domain,
            "state": state.state if state else None,
            "unit": state.attributes.get("unit_of_measurement") if state else None,
            "category": e.entity_category.value if e.entity_category else None,
            "attributes": dict(state.attributes) if state else {},
        }
    return inventory


async def _refresh(hass, entry):
    """Force a full read: refreshes requested after a write are debounced by Home Assistant."""
    await hass.data["orca"][entry.entry_id].async_refresh()
    await hass.async_block_till_done()


def _orca_errors(caplog):
    return [r.getMessage() for r in caplog.records
            if r.levelno >= logging.ERROR and "orca" in (r.name + r.getMessage())]


@pytest.mark.parametrize("name", SCENARIOS)
async def test_original_entities_unchanged(hass, pac_factory, caplog, name):
    pac, entry = await _setup(hass, pac_factory, scenarios()[name])
    inventory = _inventory(hass, entry)
    reference = BASELINE[name]["ha"]

    assert set(reference) <= set(inventory)
    changed = {
        uid: (ref, {k: inventory[uid][k] for k in ref})
        for uid, ref in reference.items()
        if {k: inventory[uid][k] for k in ref} != ref
    }
    assert not changed
    entity_ids = [e["entity_id"] for e in inventory.values()]
    assert len(entity_ids) == len(set(entity_ids))
    assert not _orca_errors(caplog)


async def test_added_families(hass, pac_factory):
    pac, entry = await _setup(hass, pac_factory, scenarios()["duo"])
    inv = _inventory(hass, entry)

    assert inv["timer1_p1_on_hour"]["domain"] == "number" and inv["timer1_p1_on_hour"]["state"] == "1"
    assert (inv["timer1_p1_on_hour"]["attributes"]["min"], inv["timer1_p1_on_hour"]["attributes"]["max"]) == (0, 23)
    assert inv["timer1_p1_off_hour"]["state"] == "23"
    assert inv["timer1_p1_mon"]["domain"] == "switch" and inv["timer1_p1_mon"]["state"] == "on"
    assert inv["legionella_temp"]["domain"] == "number" and float(inv["legionella_temp"]["state"]) == 65.0
    assert inv["legionella_turned_on"]["domain"] == "switch"
    assert inv["alarm_active"]["domain"] == "binary_sensor" and inv["alarm_active"]["state"] == "off"
    assert inv["hp_power"]["domain"] == "sensor" and float(inv["hp_power"]["state"]) == 75.0
    assert inv["compressor_hours_thousands"]["state"] == "5" and inv["compressor_hours_units"]["state"] == "862"
    assert inv["holiday_turned_on"]["domain"] == "switch"
    assert inv["wh_timer_programme"]["domain"] == "sensor" and inv["wh_timer_programme"]["state"] == "24h"
    assert inv["wh_reduced_temp"]["domain"] == "number" and float(inv["wh_reduced_temp"]["state"]) == 15.0
    assert (inv["wh_reduced_temp"]["attributes"]["min"], inv["wh_reduced_temp"]["attributes"]["max"]) == (10, 60)
    assert inv["wh_active_setpoint"]["domain"] == "sensor" and float(inv["wh_active_setpoint"]["state"]) == 44.5

    call = hass.services.async_call
    pac.writes.clear()
    await call("number", "set_value", {"entity_id": inv["timer1_p1_on_hour"]["entity_id"], "value": 6}, blocking=True)
    await call("number", "set_value", {"entity_id": inv["timer1_p1_on_minute"]["entity_id"], "value": 30}, blocking=True)
    await call("switch", "turn_off", {"entity_id": inv["timer1_p1_mon"]["entity_id"]}, blocking=True)
    await call("switch", "turn_on", {"entity_id": inv["legionella_turned_on"]["entity_id"]}, blocking=True)
    await call("number", "set_value", {"entity_id": inv["legionella_temp"]["entity_id"], "value": 62}, blocking=True)
    await call("number", "set_value", {"entity_id": inv["holiday_day"]["entity_id"], "value": 24}, blocking=True)
    await call("number", "set_value", {"entity_id": inv["wh_reduced_temp"]["entity_id"], "value": 40}, blocking=True)
    assert pac.writes == [
        ("2_TIMER_1_Ura_ON_1", "6"), ("2_TIMER_1_Minute_ON_1", "30"), ("2_TIMER_1_Ponedeljek_1", "0"),
        ("2_Legionela_vklop", "1"), ("2_Temperatura_legionela", "620"), ("2_Dan_pocitniski", "24"),
        ("2_Temp_vode_sanitarna_NIZJA", "400"),
    ]
    await _refresh(hass, entry)
    assert hass.states.get(inv["timer1_p1_on_hour"]["entity_id"]).state == "6"
    assert hass.states.get(inv["timer1_p1_mon"]["entity_id"]).state == "off"
    assert float(hass.states.get(inv["legionella_temp"]["entity_id"]).state) == 62.0

    # out of range: refused by Home Assistant, nothing is sent to the heat pump
    sent = len(pac.writes)
    with pytest.raises(Exception):
        await call("number", "set_value", {"entity_id": inv["timer1_p1_on_hour"]["entity_id"], "value": 24}, blocking=True)
    with pytest.raises(Exception):
        await call("number", "set_value", {"entity_id": inv["legionella_temp"]["entity_id"], "value": 70}, blocking=True)
    assert len(pac.writes) == sent


async def test_original_services(hass, pac_factory):
    pac, entry = await _setup(hass, pac_factory, scenarios()["duo"])
    inv = _inventory(hass, entry)
    water_heater = next(e["entity_id"] for e in inv.values() if e["domain"] == "water_heater")
    pac.writes.clear()
    await hass.services.async_call("number", "set_value", {"entity_id": inv["wh_on_diff"]["entity_id"], "value": 4.5}, blocking=True)
    await hass.services.async_call("water_heater", "set_temperature", {"entity_id": water_heater, "temperature": 51}, blocking=True)
    assert pac.writes == [("2_Diferenca_vklopa_SV", "45"), ("2_Temp_vode_sanitarna", "510")]


@pytest.mark.parametrize("name", ["no_room_sensor", "duo"])
async def test_climate(hass, pac_factory, caplog, name):
    """Thermostat: created with or without a room sensor, setpoint and on/off only."""
    values = scenarios()[name]
    values.update({
        "2_Izbira_TIMERJA_MK1": "0",        # 24h regime: a single setpoint
        "2_Temp_prostor_dnevna": "220", "2_Temp_prostor_nocna": "200",
        "2_MK1_vklop": "1", "2_Rezim_MK1": "1",  # on, heat
    })
    pac, entry = await _setup(hass, pac_factory, values)
    climate = next(e["entity_id"] for e in _inventory(hass, entry).values() if e["domain"] == "climate")
    state = hass.states.get(climate)

    assert state.state == "heat"
    assert state.attributes["hvac_modes"] == ["off", "heat"]
    assert state.attributes["temperature"] == 22.0
    assert (state.attributes["min_temp"], state.attributes["max_temp"]) == (10.0, 35.0)
    if name == "no_room_sensor":
        assert state.attributes["current_temperature"] is None
    else:
        assert state.attributes["current_temperature"] == round(int(values["2_Temp_Prostora"]) / 10, 1)
    assert not _orca_errors(caplog)

    call = hass.services.async_call
    pac.writes.clear()
    await call("climate", "set_temperature", {"entity_id": climate, "temperature": 21.5}, blocking=True)
    assert pac.writes == [("2_Temp_prostor_dnevna", "215")]
    await _refresh(hass, entry)
    assert hass.states.get(climate).attributes["temperature"] == 21.5

    # circuit off then on, through both services
    pac.writes.clear()
    await call("climate", "set_hvac_mode", {"entity_id": climate, "hvac_mode": "off"}, blocking=True)
    await _refresh(hass, entry)
    assert pac.writes == [("2_MK1_vklop", "0")] and hass.states.get(climate).state == "off"
    assert hass.states.get(climate).attributes["hvac_modes"] == ["off", "heat"]
    await call("climate", "turn_on", {"entity_id": climate}, blocking=True)
    await _refresh(hass, entry)
    assert pac.writes[-1] == ("2_MK1_vklop", "1") and hass.states.get(climate).state == "heat"
    await call("climate", "turn_off", {"entity_id": climate}, blocking=True)
    await call("climate", "set_hvac_mode", {"entity_id": climate, "hvac_mode": "heat"}, blocking=True)
    assert pac.writes[-2:] == [("2_MK1_vklop", "0"), ("2_MK1_vklop", "1")]

    # a mode that is not offered is refused; the heat pump mode is never written
    sent = len(pac.writes)
    with pytest.raises(Exception):
        await call("climate", "set_hvac_mode", {"entity_id": climate, "hvac_mode": "cool"}, blocking=True)
    with pytest.raises(Exception):
        await call("climate", "set_temperature", {"entity_id": climate, "temperature": 40}, blocking=True)
    assert len(pac.writes) == sent and not [w for w in pac.writes if w[0] == "2_Rezim_MK1"]

    # with a timer programme: two setpoints (night / day)
    pac.values["2_Izbira_TIMERJA_MK1"] = "1"
    await _refresh(hass, entry)
    attributes = hass.states.get(climate).attributes
    assert attributes["temperature"] is None
    assert (attributes["target_temp_low"], attributes["target_temp_high"]) == (20.0, 21.5)
    await call("climate", "set_temperature", {"entity_id": climate, "target_temp_low": 19, "target_temp_high": 22}, blocking=True)
    assert pac.writes[-2:] == [("2_Temp_prostor_nocna", "190"), ("2_Temp_prostor_dnevna", "220")]

    # heat pump in cooling mode: the thermostat offers off / cool
    pac.values["2_Rezim_MK1"] = "2"
    await _refresh(hass, entry)
    assert hass.states.get(climate).state == "cool"
    assert hass.states.get(climate).attributes["hvac_modes"] == ["off", "cool"]

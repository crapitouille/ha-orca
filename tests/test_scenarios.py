"""Regression tests of the hot water house scenarios (examples/scenarios-eau-chaude.yaml).

The package is loaded in a real Home Assistant instance (in memory) next to the
integration, itself connected to the heat pump simulator. The tests check what is
actually written to the heat pump for each scenario.
"""
import asyncio
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
import yaml
from homeassistant.const import MAJOR_VERSION, MINOR_VERSION
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from .helpers import scenarios
from .test_integration import _inventory, _refresh, _setup

PACKAGE = yaml.safe_load(
    (Path(__file__).parent.parent / "examples" / "scenarios-eau-chaude.yaml").read_text(encoding="utf8")
)

SCENARIO = "input_select.ecs_scenario"
P1 = "sensor.p1_meter_power"
OFFPEAK = "binary_sensor.groupe_e_tariffs_v2_double_offpeak"
INJECTION = "sensor.injection_reseau"
TIMER = "timer.ecs_maintien_surplus"
PENDING = "input_boolean.ecs_legio_en_attente"

PROGRAMME = "2_Temp_vode_sanitarna"         # setpoint during the timer programme
REDUCED = "2_Temp_vode_sanitarna_NIZJA"     # setpoint outside the timer programme
LEGIONELLA = "2_Legionela_vklop"
VALVE = "2_Preklop_PV1"                     # 1 = the heat pump is producing hot water

SETTINGS = {
    "ecs_t_confort": 55, "ecs_t_vacances": 42, "ecs_t_defaut": 45, "ecs_t_surplus": 56,
    "ecs_seuil_surplus_kw": 2.0, "ecs_maintien_min": 20,
    "ecs_seuil_prolongation_kw": 0, "ecs_legio_delai_min": 10,
}
OPTIONS_ON = ["ecs_surplus_actif", "ecs_vacances_couper_legio", "ecs_legio_apres_vacances"]
SENSOR_SELECT = "select.ecs_capteur_reseau"
OFFPEAK_SELECT = "select.ecs_capteur_heures_creuses"

# Entity IDs used by the package, as created by Home Assistant 2026.11. Older versions
# do not prefix them with the device name ("number.hot_water_reduced_temperature"): the
# fixture then adapts the package, so that the logic is tested on every version.
WATER_HEATER = "water_heater.orca_heat_pump_water_heater"
DEVICE_PREFIX = "orca_heat_pump_"
EXPECTED_ENTITIES = {
    "wh_reduced_temp": "number.orca_heat_pump_hot_water_reduced_temperature",
    "legionella_turned_on": "switch.orca_heat_pump_legionella_programme",
    "legionella_day": "number.orca_heat_pump_legionella_start_day",
    "legionella_hour": "number.orca_heat_pump_legionella_start_hour",
    "legionella_minute": "number.orca_heat_pump_legionella_start_minute",
    "valve_pos": "sensor.orca_heat_pump_position_of_3_way_valve",
}


class House:
    """Home Assistant + heat pump simulator + the scenario package."""

    def __init__(self, hass, pac, entry):
        self.hass, self.pac, self.entry = hass, pac, entry

    async def settle(self):
        """Wait until the automations have run and their writes have reached the heat pump.

        The writes are real HTTP requests to the simulator: async_block_till_done() alone
        does not wait for them on every Home Assistant version.
        """
        quiet = 0
        for _ in range(500):
            await self.hass.async_block_till_done()
            running = any(
                self.hass.states.get(a).attributes.get("current")
                for a in self.hass.states.async_entity_ids("automation")
            )
            received = len(self.pac.writes)
            await self.hass.async_add_executor_job(time.sleep, 0.02)
            await self.hass.async_block_till_done()
            quiet = 0 if running or len(self.pac.writes) != received else quiet + 1
            if quiet == 2:
                return
        raise AssertionError("the automations never settled")

    async def call(self, domain, service, entity_id, **data):
        await self.hass.services.async_call(domain, service, {"entity_id": entity_id, **data}, blocking=True)
        await self.settle()

    async def select(self, option):
        await self.call("input_select", "select_option", SCENARIO, option=option)

    async def grid_power(self, watts):
        """Power at the grid meter: negative when the house exports."""
        self.hass.states.async_set(P1, str(watts), {"unit_of_measurement": "W", "device_class": "power"})
        await self.settle()

    async def offpeak(self, state):
        self.hass.states.async_set(OFFPEAK, state)
        await self.settle()

    async def hot_water_production(self, running):
        self.pac.values[VALVE] = "1" if running else "0"
        await _refresh(self.hass, self.entry)
        await self.settle()

    async def end_of_hold(self):
        """Jump to the end of the surplus hold timer."""
        async_fire_time_changed(
            self.hass, dt_util.utcnow() + timedelta(minutes=SETTINGS["ecs_maintien_min"], seconds=1)
        )
        await self.settle()

    async def flush_templates(self):
        """Let the rate-limited template updates run.

        Templates that list a whole domain (the sensor choices) are refreshed at most once
        per second, on the event loop's real clock.
        """
        await asyncio.sleep(1.2)
        await self.settle()

    def state(self, entity_id):
        return self.hass.states.get(entity_id).state

    def writes(self):
        """Writes received by the heat pump since the last call."""
        done = list(self.pac.writes)
        self.pac.writes.clear()
        return done


@pytest.fixture
async def house(hass, pac_factory):
    await hass.config.async_set_time_zone("Europe/Zurich")
    values = scenarios()["duo"]
    values.update({                      # as found on the reference installation
        PROGRAMME: "550", REDUCED: "450", LEGIONELLA: "1",
        "2_On_Dan_Legionella": "1", "2_On_Ura_Legionella": "14", "2_On_Min_Legionella": "0",
        VALVE: "0",
    })
    pac, entry = await _setup(hass, pac_factory, values)
    h = House(hass, pac, entry)
    await h.grid_power(300)
    await h.offpeak("off")
    for domain in ("input_select", "input_number", "input_boolean", "input_text", "timer", "template"):
        assert await async_setup_component(hass, domain, {domain: PACKAGE[domain]})
    await hass.async_block_till_done()
    for name, value in SETTINGS.items():
        await h.call("input_number", "set_value", f"input_number.{name}", value=value)
    for name in OPTIONS_ON:
        await h.call("input_boolean", "turn_on", f"input_boolean.{name}")
    await h.call("select", "select_option", SENSOR_SELECT, option=P1)
    await h.call("select", "select_option", OFFPEAK_SELECT, option=OFFPEAK)
    inv = _inventory(hass, entry)
    automations = json.dumps(PACKAGE["automation"])
    actual = {expected: inv[unique_id]["entity_id"] for unique_id, expected in EXPECTED_ENTITIES.items()}
    actual[WATER_HEATER] = next(e["entity_id"] for e in inv.values() if e["domain"] == "water_heater")
    for expected, entity_id in actual.items():
        assert expected in automations
        automations = automations.replace(expected, entity_id)
    assert await async_setup_component(hass, "automation", {"automation": json.loads(automations)})
    await h.settle()
    assert h.writes() == []              # loading the package writes nothing
    yield h
    await hass.services.async_call("timer", "cancel", {"entity_id": TIMER}, blocking=True)
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    # The sensor choice lists are rate-limited templates: a refresh may still be scheduled
    # after the last sensor update (the unload above being the last one). Home Assistant
    # does not cancel it when it stops.
    for handle in list(hass.loop._scheduled):
        if "TrackTemplateResultInfo._refresh" in repr(handle):
            handle.cancel()


async def test_package_entities(house):
    """The package loads and targets entities that exist."""
    inv = _inventory(house.hass, house.entry)
    actual = {expected: inv[unique_id]["entity_id"] for unique_id, expected in EXPECTED_ENTITIES.items()}
    actual[WATER_HEATER] = next(e["entity_id"] for e in inv.values() if e["domain"] == "water_heater")
    for expected, entity_id in actual.items():
        assert entity_id in (expected, expected.replace(DEVICE_PREFIX, "", 1))
    if (MAJOR_VERSION, MINOR_VERSION) >= (2026, 10):
        assert all(expected == entity_id for expected, entity_id in actual.items())
    automations = house.hass.states.async_entity_ids("automation")
    assert len(automations) == 3 and all(house.state(a) == "on" for a in automations)
    assert house.state(SCENARIO) == "Économique"
    assert float(house.state(INJECTION)) == -0.3


async def test_confort(house):
    await house.select("Confort")
    assert house.writes() == [(PROGRAMME, "550"), (REDUCED, "550")]

    # export above the threshold: no effect outside the Économique scenario
    await house.grid_power(-3500)
    assert house.writes() == [] and house.state(TIMER) == "idle"

    # a modified setpoint is applied at once
    await house.call("input_number", "set_value", "input_number.ecs_t_confort", value=53.5)
    assert house.writes() == [(PROGRAMME, "535"), (REDUCED, "535")]
    # a setpoint of another scenario: the current scenario is applied again, unchanged
    await house.call("input_number", "set_value", "input_number.ecs_t_vacances", value=40)
    assert house.writes() == [(PROGRAMME, "535"), (REDUCED, "535")]


async def test_vacances(house):
    await house.select("Vacances")
    assert house.writes() == [(PROGRAMME, "420"), (REDUCED, "420"), (LEGIONELLA, "0")]
    assert house.state(PENDING) == "off"

    await house.grid_power(-3500)
    assert house.writes() == [] and house.state(TIMER) == "idle"


async def test_economique_without_surplus(house):
    await house.select("Confort")
    house.writes()
    await house.select("Économique")
    assert house.writes() == [(REDUCED, "450"), (PROGRAMME, "450")]
    assert house.state(TIMER) == "idle"

    # export below the threshold: nothing happens
    await house.grid_power(-1900)
    assert house.writes() == [] and house.state(TIMER) == "idle"


async def test_economique_surplus_hold_and_return(house):
    await house.select("Confort")
    await house.select("Économique")
    house.writes()

    await house.grid_power(-2500)
    assert float(house.state(INJECTION)) == 2.5
    assert house.writes() == [(PROGRAMME, "560")]
    assert house.state(TIMER) == "active"
    assert house.hass.states.get(TIMER).attributes["duration"] == "0:20:00"

    # the export drops during the hold: the high setpoint stays
    await house.grid_power(400)
    assert house.writes() == [] and house.state(TIMER) == "active"

    # end of the hold, no surplus left: back to the default setpoint
    await house.end_of_hold()
    assert house.writes() == [(PROGRAMME, "450")]
    assert house.state(TIMER) == "idle"

    # the reduced setpoint is never touched by the surplus logic
    assert house.pac.values[REDUCED] == "450"


async def test_economique_surplus_is_extended(house):
    await house.select("Confort")
    await house.select("Économique")
    house.writes()
    await house.grid_power(-2500)
    assert house.writes() == [(PROGRAMME, "560")]

    # still above the threshold at the end of the hold: extended, nothing written
    await house.end_of_hold()
    assert house.writes() == [] and house.state(TIMER) == "active"

    # the heat pump is heating the tank and the house still exports a little:
    # extended too, otherwise the compressor would be stopped by its own consumption
    await house.hot_water_production(True)
    await house.grid_power(-300)
    await house.end_of_hold()
    assert house.writes() == [] and house.state(TIMER) == "active"

    # heating the tank from the grid: back to the default setpoint
    await house.grid_power(900)
    await house.end_of_hold()
    assert house.writes() == [(PROGRAMME, "450")] and house.state(TIMER) == "idle"

    # a new surplus starts a new hold
    await house.grid_power(-2100)
    assert house.writes() == [(PROGRAMME, "560")] and house.state(TIMER) == "active"

    # the surplus setpoint is modified during a hold: applied at once
    await house.call("input_number", "set_value", "input_number.ecs_t_surplus", value=58)
    assert house.writes() == [(PROGRAMME, "580")]
    # the default setpoint is modified while the house exports: the high setpoint is confirmed
    await house.call("input_number", "set_value", "input_number.ecs_t_defaut", value=44)
    assert house.writes() == [(REDUCED, "440"), (PROGRAMME, "580")]
    # modified during a hold, without surplus: only the reduced setpoint follows
    await house.grid_power(400)
    await house.call("input_number", "set_value", "input_number.ecs_t_defaut", value=43.5)
    assert house.writes() == [(REDUCED, "435")] and house.state(TIMER) == "active"


async def test_economique_selected_while_exporting(house):
    await house.select("Confort")
    house.writes()
    await house.grid_power(-3000)
    await house.select("Économique")
    assert house.writes() == [(REDUCED, "450"), (PROGRAMME, "560")]
    assert house.state(TIMER) == "active"


async def test_leaving_economique_cancels_the_hold(house):
    await house.select("Confort")
    await house.select("Économique")
    await house.grid_power(-2500)
    assert house.state(TIMER) == "active"
    house.writes()

    await house.select("Confort")
    assert house.state(TIMER) == "idle"
    assert house.writes() == [(PROGRAMME, "550"), (REDUCED, "550")]
    await house.end_of_hold()
    assert house.writes() == []


async def test_threshold_and_duration_settings(house):
    await house.select("Confort")
    await house.select("Économique")
    house.writes()
    await house.call("input_number", "set_value", "input_number.ecs_seuil_surplus_kw", value=3)
    await house.call("input_number", "set_value", "input_number.ecs_maintien_min", value=45)

    await house.grid_power(-2500)
    assert house.writes() == []
    await house.grid_power(-3100)
    assert house.writes() == [(PROGRAMME, "560")]
    assert house.hass.states.get(TIMER).attributes["duration"] == "0:45:00"


async def test_no_grid_meter(house):
    """Without a grid meter the injection sensor is unavailable: Économique stays at the default."""
    house.hass.states.async_set(P1, "unavailable")
    await house.settle()
    assert house.state(INJECTION) == "unavailable"

    await house.select("Confort")
    house.writes()
    await house.select("Économique")
    assert house.writes() == [(REDUCED, "450"), (PROGRAMME, "450")]
    assert house.state(TIMER) == "idle"


def _legionella_writes(day, hour, minute):
    return [
        ("2_On_Dan_Legionella", str(day)), ("2_On_Ura_Legionella", str(hour)),
        ("2_On_Min_Legionella", str(minute)), (LEGIONELLA, "1"),
    ]


@pytest.mark.parametrize(
    ("back_to", "now", "expected"),
    [
        # Monday 16 November 2026, 22:00 -> cycle programmed on Monday (1) at 22:10
        ("Confort", datetime(2026, 11, 16, 22, 0), (1, 22, 10)),
        # Sunday 22 November 2026, 23:55 -> the cycle falls on Monday (1) at 00:05
        ("Économique", datetime(2026, 11, 22, 23, 55), (1, 0, 5)),
        # Saturday 21 November 2026, 06:07 -> Saturday (6) at 06:17
        ("Confort", datetime(2026, 11, 21, 6, 7), (6, 6, 17)),
        # Sunday 28 March 2027, summer time -> Sunday (7) at 21:40
        ("Économique", datetime(2027, 3, 28, 21, 30), (7, 21, 40)),
    ],
)
async def test_legionella_at_next_offpeak_after_holidays(house, freezer, back_to, now, expected):
    await house.select("Vacances")
    house.writes()

    # back from holidays during peak hours: setpoints at once, the cycle waits
    await house.select(back_to)
    setpoints = [(PROGRAMME, "550"), (REDUCED, "550")] if back_to == "Confort" else [(REDUCED, "450"), (PROGRAMME, "450")]
    assert house.writes() == setpoints
    assert house.state(PENDING) == "on"

    freezer.move_to(now.replace(tzinfo=ZoneInfo("Europe/Zurich")))
    await house.offpeak("on")
    assert house.writes() == _legionella_writes(*expected)
    assert house.state(PENDING) == "off"

    # the following off-peak periods do nothing
    await house.offpeak("off")
    await house.offpeak("on")
    assert house.writes() == []


async def test_legionella_at_once_when_back_during_offpeak(house, freezer):
    await house.select("Vacances")
    house.writes()
    await house.offpeak("on")
    assert house.writes() == []          # still on holidays: nothing

    freezer.move_to(datetime(2026, 11, 18, 2, 15, tzinfo=ZoneInfo("Europe/Zurich")))
    await house.select("Confort")
    writes = house.writes()
    assert sorted(writes) == sorted([(PROGRAMME, "550"), (REDUCED, "550")] + _legionella_writes(3, 2, 25))
    # whatever the interleaving of the two automations, the legionella writes keep their order
    assert [w for w in writes if w[0] not in (PROGRAMME, REDUCED)] == _legionella_writes(3, 2, 25)
    assert house.state(PENDING) == "off"


async def test_no_legionella_if_back_on_holidays_before_offpeak(house):
    await house.select("Vacances")
    await house.select("Confort")
    assert house.state(PENDING) == "on"
    await house.select("Vacances")
    assert house.state(PENDING) == "off"
    house.writes()

    await house.offpeak("on")
    assert house.writes() == []
    assert house.pac.values[LEGIONELLA] == "0"


async def test_no_legionella_without_holidays(house):
    """Switching between Économique and Confort never touches the legionella programme."""
    await house.offpeak("on")
    await house.select("Confort")
    await house.select("Économique")
    await house.select("Confort")
    await house.offpeak("off")
    await house.offpeak("on")
    assert house.state(PENDING) == "off"
    assert not [w for w in house.writes() if "Legionel" in w[0]]


# --- settings made editable from the dashboard ------------------------------------------


async def test_sensor_choice_from_the_dashboard(house):
    """The grid and off-peak sensors are chosen in lists; unit and sign are handled."""
    hass = house.hass
    await house.select("Confort")          # no hot water boost while the meters change
    house.writes()
    assert P1 in hass.states.get(SENSOR_SELECT).attributes["options"]
    assert INJECTION not in hass.states.get(SENSOR_SELECT).attributes["options"]
    assert OFFPEAK in hass.states.get(OFFPEAK_SELECT).attributes["options"]
    assert house.state(SENSOR_SELECT) == P1 and house.state("input_text.ecs_capteur_reseau") == P1
    assert house.state("binary_sensor.ecs_heure_creuse") == "off"

    # another meter, in kW and positive when exporting
    hass.states.async_set("sensor.compteur_kw", "2.5", {"unit_of_measurement": "kW", "device_class": "power"})
    await house.flush_templates()
    await house.call("select", "select_option", SENSOR_SELECT, option="sensor.compteur_kw")
    assert float(house.state(INJECTION)) == -2.5
    await house.call("input_boolean", "turn_on", "input_boolean.ecs_reseau_injection_positive")
    assert float(house.state(INJECTION)) == 2.5

    # another off-peak signal
    hass.states.async_set("binary_sensor.autre_tarif", "on")
    await house.flush_templates()
    await house.call("select", "select_option", OFFPEAK_SELECT, option="binary_sensor.autre_tarif")
    assert house.state("binary_sensor.ecs_heure_creuse") == "on"
    assert house.writes() == []


async def test_surplus_can_be_disabled(house):
    await house.select("Confort")
    await house.select("Économique")
    await house.call("input_boolean", "turn_off", "input_boolean.ecs_surplus_actif")
    house.writes()

    await house.grid_power(-3000)
    assert house.writes() == [] and house.state(TIMER) == "idle"
    await house.select("Confort")
    await house.select("Économique")
    assert house.writes()[-1] == (PROGRAMME, "450")

    # enabled again while exporting: the hold starts at once
    await house.call("input_boolean", "turn_on", "input_boolean.ecs_surplus_actif")
    assert house.writes() == [(PROGRAMME, "560")] and house.state(TIMER) == "active"

    # disabled during a hold: back to the default setpoint
    await house.call("input_boolean", "turn_off", "input_boolean.ecs_surplus_actif")
    assert house.writes() == [(PROGRAMME, "450")] and house.state(TIMER) == "idle"


async def test_extension_threshold_setting(house):
    await house.select("Confort")
    await house.select("Économique")
    await house.call("input_number", "set_value", "input_number.ecs_seuil_prolongation_kw", value=0.5)
    await house.grid_power(-2500)
    house.writes()

    # heating the tank, the house exports 0.3 kW: below the extension threshold
    await house.hot_water_production(True)
    await house.grid_power(-300)
    await house.end_of_hold()
    assert house.writes() == [(PROGRAMME, "450")] and house.state(TIMER) == "idle"

    # 0.8 kW: above it, the hold is extended
    await house.grid_power(-2500)
    house.writes()
    await house.grid_power(-800)
    await house.end_of_hold()
    assert house.writes() == [] and house.state(TIMER) == "active"


async def test_legionella_delay_setting(house, freezer):
    await house.call("input_number", "set_value", "input_number.ecs_legio_delai_min", value=25)
    await house.select("Vacances")
    await house.select("Confort")
    house.writes()
    freezer.move_to(datetime(2026, 11, 17, 22, 50, tzinfo=ZoneInfo("Europe/Zurich")))
    await house.offpeak("on")
    # Tuesday 22:50 + 25 min -> Tuesday (2) at 23:15
    assert house.writes() == _legionella_writes(2, 23, 15)


async def test_holidays_without_cutting_legionella(house):
    await house.call("input_boolean", "turn_off", "input_boolean.ecs_vacances_couper_legio")
    await house.select("Vacances")
    assert house.writes() == [(PROGRAMME, "420"), (REDUCED, "420")]
    assert house.pac.values[LEGIONELLA] == "1"
    await house.select("Confort")
    assert house.state(PENDING) == "on"     # the cycle after holidays is still asked for


async def test_return_without_legionella_cycle(house):
    """Option off: the programme cut during the holidays is switched on again as it was."""
    await house.call("input_boolean", "turn_off", "input_boolean.ecs_legio_apres_vacances")
    await house.select("Vacances")
    house.writes()
    await house.select("Économique")
    writes = house.writes()
    assert (LEGIONELLA, "1") in writes
    assert not [w for w in writes if w[0].startswith("2_On_")]   # day and hour unchanged
    assert house.state(PENDING) == "off"
    await house.offpeak("on")
    assert house.writes() == []


async def test_cycle_cancelled_while_pending(house):
    await house.select("Vacances")
    await house.select("Confort")
    assert house.state(PENDING) == "on"
    house.writes()
    await house.call("input_boolean", "turn_off", "input_boolean.ecs_legio_apres_vacances")
    assert house.writes() == [(LEGIONELLA, "1")]
    assert house.state(PENDING) == "off"
    await house.offpeak("on")
    assert house.writes() == []

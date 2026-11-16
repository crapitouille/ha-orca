"""Regression tests of the API client against the heat pump simulator.

For every scenario, the original entities must be exactly what upstream 2.4.3
returned (tests/fixtures/baseline_2.4.3.json).
"""
import pytest

from custom_components.orca.orca_api import OrcaApi

from .helpers import BASELINE, api_snapshot, scenarios

SCENARIOS = ["duo", "mono", "no_room_sensor"]


async def _client(pac_factory, values, circuits=None):
    pac, host = await pac_factory(values)
    api = OrcaApi("admin", "admin", host)
    await api.initialize(circuits_override=circuits)
    return api, pac


@pytest.mark.parametrize("name", SCENARIOS)
async def test_original_entities_unchanged(pac_factory, name):
    api, pac = await _client(pac_factory, scenarios()[name])
    snap = api_snapshot(await api.fetch_all())
    reference = BASELINE[name]

    assert api.available_circuits == reference["circuits"]
    assert set(reference["api"]) <= set(snap)
    changed = {k: (v, snap[k]) for k, v in reference["api"].items() if snap[k] != v}
    # The only intended difference with 2.4.3: the hot water setpoint is limited to 55 °C (2.5.3).
    desired = changed.pop("wh_desired_temp")
    assert not changed
    differing = {key for key in desired[0] if desired[0][key] != desired[1][key]}
    assert len(differing) == 1 and "55.0" in str(desired[1]) and "60.0" in str(desired[0])

    original_tags = {v["tag"] for v in reference["api"].values()}
    added = {k: v for k, v in snap.items() if k not in reference["api"]}
    assert added, "the added families are missing"
    assert not {v["tag"] for v in added.values()} & original_tags
    assert all(v["platform"] not in ("none", "excluded") for v in added.values())


@pytest.mark.parametrize("name", SCENARIOS)
async def test_original_writes_unchanged(pac_factory, name):
    """Each original setting written back with its current value sends the same request."""
    api, pac = await _client(pac_factory, scenarios()[name])
    snap = api_snapshot(await api.fetch_all())
    pac.writes.clear()
    for uid, item in BASELINE[name]["api"].items():
        if item["adjustable"]["enabled"]:
            await api.set_value_by_id(uid, snap[uid]["value"])
    assert sorted(list(w) for w in pac.writes) == sorted(BASELINE[name]["writes"])


async def test_read_batches_stay_small(pac_factory):
    api, pac = await _client(pac_factory, scenarios()["duo"])
    await api.fetch_all()
    assert max(pac.read_batches) <= 100


async def test_forced_circuits(pac_factory):
    api, _ = await _client(pac_factory, scenarios()["duo"], circuits=[1, 4])
    assert api.available_circuits == [0, 1, 4]


async def test_unavailable_tags_are_skipped(pac_factory):
    values = scenarios()["duo"]
    values.update({"2_TIMER_1_Ura_ON_1": "-9999", "2_Legionela_MAX_CAS": "", "2_JE_ALARM": "-9999"})
    api, _ = await _client(pac_factory, values)
    snap = api_snapshot(await api.fetch_all())
    assert not {"timer1_p1_on_hour", "legionella_max_time", "alarm_active"} & set(snap)
    assert "timer1_p1_off_hour" in snap


async def test_integer_and_boolean_writes(pac_factory):
    api, pac = await _client(pac_factory, scenarios()["duo"])
    await api.set_value_by_id("timer1_p1_on_hour", 22.0)  # Home Assistant sends floats
    await api.set_value_by_id("timer1_p1_off_minute", 30)
    await api.set_value_by_id("timer1_p1_mon", True)
    assert pac.writes == [
        ("2_TIMER_1_Ura_ON_1", "22"),
        ("2_TIMER_1_Minute_OFF_1", "30"),
        ("2_TIMER_1_Ponedeljek_1", "1"),
    ]
    values = {v.config.unique_id: v.value for v in await api.fetch_all()}
    assert values["timer1_p1_on_hour"] == 22 and values["timer1_p1_mon"] is True


@pytest.mark.parametrize("bad", [24, -1, 7.5, "abc", None])
async def test_integer_write_rejects_invalid_values(pac_factory, bad):
    api, pac = await _client(pac_factory, scenarios()["duo"])
    with pytest.raises(ValueError):
        await api.set_value_by_id("timer1_p1_on_hour", bad)
    assert pac.writes == []


async def test_legionella_temperature_is_bounded(pac_factory):
    api, pac = await _client(pac_factory, scenarios()["duo"])
    await api.set_value_by_id("legionella_temp", 62.5)
    assert pac.writes == [("2_Temperatura_legionela", "625")]
    for bad in (66, 59.5):
        with pytest.raises(ValueError):
            await api.set_value_by_id("legionella_temp", bad)
    assert len(pac.writes) == 1


async def test_read_only_tags_cannot_be_written(pac_factory):
    api, pac = await _client(pac_factory, scenarios()["duo"])
    with pytest.raises(ValueError):
        await api.set_value_by_id("alarm_active", True)
    assert pac.writes == []


async def test_hot_water_reduced_temperature(pac_factory):
    """Lower temperature regime of the hot water (outside the timer programme)."""
    api, pac = await _client(pac_factory, scenarios()["duo"])
    snap = api_snapshot(await api.fetch_all())
    assert snap["wh_reduced_temp"]["value"] == 15.0 and snap["wh_reduced_temp"]["platform"] == "number"
    assert snap["wh_active_setpoint"]["value"] == 44.5 and snap["wh_active_setpoint"]["platform"] == "sensor"
    await api.set_value_by_id("wh_reduced_temp", 40)
    assert pac.writes == [("2_Temp_vode_sanitarna_NIZJA", "400")]
    for bad in (9.9, 55.5):
        with pytest.raises(ValueError):
            await api.set_value_by_id("wh_reduced_temp", bad)
    with pytest.raises(ValueError):
        await api.set_value_by_id("wh_active_setpoint", 50)
    assert len(pac.writes) == 1

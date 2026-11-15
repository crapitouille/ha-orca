"""Rebuild baseline_2.4.3.json from an unmodified checkout of the upstream integration.

The baseline is what Tomasinjo/orca-energy-ha 2.4.3 (commit 73a8741) returns for each
scenario. The regression tests check that this fork still returns exactly the same
thing for every original entity. It only needs regenerating when the reference
version changes.

    python tests/fixtures/make_baseline.py /path/to/orca-energy-ha/custom_components/orca \\
        [ha_inventory_duo.json ha_inventory_mono.json ha_inventory_no_room_sensor.json]

The optional files are Home Assistant entity inventories of the upstream version
(see tests/test_integration.py::test_original_entities_unchanged for the format).
"""
import asyncio
import importlib.util
import json
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.helpers import api_snapshot, scenarios  # noqa: E402
from tests.mock_pac import MockPac  # noqa: E402


def load_upstream(pkg_dir: Path):
    """Load models.py and orca_api.py without running __init__.py."""
    pkg = types.ModuleType("orca_upstream")
    pkg.__path__ = [str(pkg_dir)]
    sys.modules["orca_upstream"] = pkg
    for name in ("models", "orca_api"):
        spec = importlib.util.spec_from_file_location(f"orca_upstream.{name}", pkg_dir / f"{name}.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[f"orca_upstream.{name}"] = mod
        spec.loader.exec_module(mod)
    return sys.modules["orca_upstream.orca_api"]


async def main():
    upstream = load_upstream(Path(sys.argv[1]))
    inventories = sys.argv[2:5]
    baseline = {}
    for index, (name, values) in enumerate(scenarios().items()):
        pac = MockPac(values)
        host = await pac.start()
        api = upstream.OrcaApi("admin", "admin", host)
        await api.initialize()
        snap = api_snapshot(await api.fetch_all())
        pac.writes.clear()
        for uid, item in snap.items():
            if item["adjustable"]["enabled"]:
                await api.set_value_by_id(uid, item["value"])
        baseline[name] = {"circuits": api.available_circuits, "api": snap, "writes": pac.writes}
        if inventories:
            entities = json.loads(Path(inventories[index]).read_text(encoding="utf8"))["entities"]
            baseline[name]["ha"] = {
                uid: {k: e[k] for k in ("domain", "state", "unit", "category")}
                for uid, e in sorted(entities.items())
                if e["domain"] != "climate"
            }
        await pac.stop()
    out = Path(__file__).parent / "baseline_2.4.3.json"
    out.write_text(json.dumps(baseline, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf8")
    print({k: (len(v["api"]), len(v.get("ha", {}))) for k, v in baseline.items()})


asyncio.run(main())

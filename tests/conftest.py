"""Shared pytest fixtures for Openpasture tests."""

from __future__ import annotations

import pytest

from openpasture.runtime import reset_runtime


@pytest.fixture(autouse=True)
def isolated_runtime(tmp_path, monkeypatch):
    """Give each test an isolated local data directory."""
    monkeypatch.setenv("OPENPASTURE_DATA_DIR", str(tmp_path / ".openpasture"))
    monkeypatch.setenv("OPENPASTURE_STORE", "sqlite")
    monkeypatch.setenv("OPENPASTURE_LOAD_SEED", "0")
    # Offline, deterministic connectors: fixture land data and simulated collars.
    monkeypatch.setenv("OPENPASTURE_LAND_SOURCE", "fixture")
    monkeypatch.setenv("OPENPASTURE_COLLAR_GATEWAY", "simulated")
    reset_runtime()
    yield
    reset_runtime()


# Two adjacent, mapped paddocks (they share the -92.40 fence line) on one farm.
HOME = {"type": "Polygon", "coordinates": [[[-92.41, 38.12], [-92.40, 38.12], [-92.40, 38.13], [-92.41, 38.13], [-92.41, 38.12]]]}
NORTH = {"type": "Polygon", "coordinates": [[[-92.40, 38.12], [-92.39, 38.12], [-92.39, 38.13], [-92.40, 38.13], [-92.40, 38.12]]]}
COLLAR_IDS = ("oc_0012", "oc_0013", "oc_0014")


@pytest.fixture
def collared_farm():
    """A farm with a herd in paddock_home wearing three simulated collars."""

    import json
    from types import SimpleNamespace

    from openpasture.context import get_collar_service
    from openpasture.runtime import initialize
    from openpasture.tools.collar import handle_record_collar_report
    from openpasture.tools.farm import handle_add_paddock, handle_register_farm, handle_set_herd_position

    initialize()
    farm = json.loads(
        handle_register_farm(
            {
                "name": "Willow Creek",
                "timezone": "America/Chicago",
                "location": {"longitude": -92.40, "latitude": 38.125},
                "herd": {"id": "herd_1", "species": "cattle", "count": 28},
            }
        )
    )["farm"]
    handle_add_paddock({"farm_id": farm["id"], "paddock_id": "paddock_home", "name": "Home", "status": "grazing", "geometry": HOME})
    handle_add_paddock({"farm_id": farm["id"], "paddock_id": "paddock_north", "name": "North", "status": "resting", "geometry": NORTH})
    handle_set_herd_position({"herd_id": "herd_1", "paddock_id": "paddock_home"})

    gateway = get_collar_service().gateway
    for collar_id in COLLAR_IDS:
        report = gateway.simulate_report(collar_id, HOME, count=4)
        handle_record_collar_report({"farm_id": farm["id"], "herd_id": "herd_1", "report": report})
    return SimpleNamespace(
        farm_id=farm["id"], herd_id="herd_1", gateway=gateway, home=HOME, north=NORTH, collar_ids=COLLAR_IDS
    )

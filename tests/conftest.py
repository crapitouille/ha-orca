"""Test configuration."""
import custom_components  # noqa: F401  must be imported before the plugin's own test folder

import pytest

from .mock_pac import MockPac


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Let Home Assistant load the integration from custom_components/."""
    yield


@pytest.fixture
async def pac_factory(socket_enabled):
    """Start heat pump simulators on localhost; stop them after the test."""
    started = []

    async def _start(values):
        pac = MockPac(values)
        host = await pac.start()
        started.append(pac)
        return pac, host

    yield _start
    for pac in started:
        await pac.stop()

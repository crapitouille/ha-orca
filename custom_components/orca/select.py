"""Select platform for Orca integration: adjustable settings with named choices."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, EXCLUDED_IDS
from .coordinator import OrcaDataUpdateCoordinator
from .entity import OrcaEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Orca selects."""
    coordinator: OrcaDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        OrcaSelect(coordinator, unique_id)
        for unique_id, tag_value in coordinator.data.items()
        if tag_value.config.type == "multimode"
        and tag_value.config.adjustable.enabled
        and tag_value.config.id not in EXCLUDED_IDS
    )


class OrcaSelect(OrcaEntity, SelectEntity):
    """Representation of an adjustable Orca setting with named choices."""

    def __init__(self, coordinator: OrcaDataUpdateCoordinator, unique_id: str) -> None:
        """Initialize."""
        super().__init__(coordinator, unique_id)
        self._attr_options = list(self.tag_data.config.value_map.values())

    @property
    def current_option(self) -> str | None:
        """Return the selected choice, None when the heat pump returns an unknown value."""
        return self.tag_data.value

    async def async_select_option(self, option: str) -> None:
        """Change the selected choice."""
        await self.coordinator.api.set_value_by_id(self.unique_id_, option)
        await self.coordinator.async_request_refresh()

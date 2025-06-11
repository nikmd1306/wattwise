"""Inline keyboard builders."""

from aiogram.filters.callback_data import CallbackData


class AdminActionCallback(CallbackData, prefix="adm"):
    """
    Callback data for admin actions.
    - stm: select_tenant_for_meter
    - stt: select_tenant_for_tariff
    - smt: select_meter_for_tariff
    """

    action: str
    entity_id: str


class SelectTenantCallback(CallbackData, prefix="usr_tenant"):
    """Callback data for selecting a tenant."""

    tenant_id: str


class SelectMeterCallback(CallbackData, prefix="mtr"):
    """Callback data for selecting a meter."""

    id: str

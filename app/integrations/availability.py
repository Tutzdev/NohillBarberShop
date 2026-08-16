from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from flask import current_app

from app.common.errors import IntegrationUnavailableError


class AvailabilityStatus(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    BARBER_NOT_FOUND = "barber_not_found"
    SERVICE_NOT_FOUND = "service_not_found"


@dataclass(frozen=True, slots=True)
class AvailabilityDecision:
    status: AvailabilityStatus
    end_at: datetime | None = None


class AvailabilityGateway(Protocol):
    def check(
        self,
        *,
        barber_id: int,
        service_id: int,
        start_at: datetime,
        exclude_appointment_id: int | None = None,
    ) -> AvailabilityDecision: ...


class UnconfiguredAvailabilityGateway:
    def check(
        self,
        *,
        barber_id: int,
        service_id: int,
        start_at: datetime,
        exclude_appointment_id: int | None = None,
    ) -> AvailabilityDecision:
        raise IntegrationUnavailableError("de disponibilidade")


def get_availability_gateway() -> AvailabilityGateway:
    return current_app.extensions.get("availability_gateway", UnconfiguredAvailabilityGateway())

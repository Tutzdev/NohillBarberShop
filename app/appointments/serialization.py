from app.appointments.models import Appointment
from app.common.time import isoformat_utc


def serialize_appointment(appointment: Appointment) -> dict:
    return {
        "id": appointment.id,
        "customer_id": appointment.customer_id,
        "barber_id": appointment.barber_id,
        "service_id": appointment.service_id,
        "start_at": isoformat_utc(appointment.start_at),
        "end_at": isoformat_utc(appointment.end_at),
        "status": appointment.status.value,
        "cancelled_at": isoformat_utc(appointment.cancelled_at),
        "version": appointment.version_id,
        "created_at": isoformat_utc(appointment.created_at),
        "updated_at": isoformat_utc(appointment.updated_at),
    }

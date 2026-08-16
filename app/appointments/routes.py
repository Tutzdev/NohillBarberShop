from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.appointments.schemas import (
    AppointmentListQuerySchema,
    CreateAppointmentSchema,
    RescheduleAppointmentSchema,
)
from app.appointments.serialization import serialize_appointment
from app.appointments.service import (
    cancel_appointment,
    create_appointment,
    get_customer_appointment,
    list_customer_appointments,
    reschedule_appointment,
)
from app.auth.jwt_callbacks import get_current_customer
from app.common.responses import success
from app.common.schemas import load_json

blueprint = Blueprint("appointments", __name__)


@blueprint.post("")
@jwt_required()
def create():
    data = load_json(request, CreateAppointmentSchema())
    appointment = create_appointment(get_current_customer(), **data)
    return success(serialize_appointment(appointment), 201)


@blueprint.get("/me")
@jwt_required()
def own_appointments():
    query = AppointmentListQuerySchema().load(request.args)
    appointments, total = list_customer_appointments(get_current_customer(), **query)
    return success(
        {
            "items": [serialize_appointment(item) for item in appointments],
            "page": query["page"],
            "per_page": query["per_page"],
            "total": total,
        }
    )


@blueprint.get("/<int:appointment_id>")
@jwt_required()
def detail(appointment_id: int):
    appointment = get_customer_appointment(get_current_customer(), appointment_id)
    return success(serialize_appointment(appointment))


@blueprint.patch("/<int:appointment_id>/cancel")
@jwt_required()
def cancel(appointment_id: int):
    appointment = cancel_appointment(get_current_customer(), appointment_id)
    return success(serialize_appointment(appointment))


@blueprint.patch("/<int:appointment_id>/reschedule")
@jwt_required()
def reschedule(appointment_id: int):
    data = load_json(request, RescheduleAppointmentSchema())
    appointment = reschedule_appointment(get_current_customer(), appointment_id, **data)
    return success(serialize_appointment(appointment))

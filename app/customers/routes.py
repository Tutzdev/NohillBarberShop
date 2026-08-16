from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.auth.jwt_callbacks import get_current_customer
from app.common.responses import success
from app.common.schemas import load_json
from app.customers.schemas import UpdateCustomerSchema
from app.customers.serialization import serialize_customer
from app.customers.service import update_customer

blueprint = Blueprint("customers", __name__)


@blueprint.get("/me")
@jwt_required()
def own_profile():
    return success(serialize_customer(get_current_customer()))


@blueprint.patch("/me")
@jwt_required()
def update_own_profile():
    changes = load_json(request, UpdateCustomerSchema())
    customer = update_customer(get_current_customer(), changes)
    return success(serialize_customer(customer))

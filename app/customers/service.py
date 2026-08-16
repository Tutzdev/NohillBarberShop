from sqlalchemy.exc import IntegrityError

from app.common.errors import ConflictError
from app.config.extensions import db
from app.customers.models import Customer

UPDATABLE_FIELDS = frozenset({"name", "email", "phone"})


def update_customer(customer: Customer, changes: dict) -> Customer:
    if not changes:
        return customer

    for field in UPDATABLE_FIELDS:
        if field in changes:
            setattr(customer, field, changes[field])

    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ConflictError(
            "EMAIL_ALREADY_REGISTERED", "Já existe uma conta com este e-mail."
        ) from exc
    return customer

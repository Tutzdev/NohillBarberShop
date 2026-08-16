from app.common.time import isoformat_utc
from app.customers.models import Customer


def serialize_customer(customer: Customer) -> dict:
    return {
        "id": customer.id,
        "name": customer.name,
        "email": customer.email,
        "phone": customer.phone,
        "created_at": isoformat_utc(customer.created_at),
        "updated_at": isoformat_utc(customer.updated_at),
    }

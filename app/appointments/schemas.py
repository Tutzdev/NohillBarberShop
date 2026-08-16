from marshmallow import RAISE, Schema, ValidationError, fields, validates


class CreateAppointmentSchema(Schema):
    class Meta:
        unknown = RAISE

    barber_id = fields.Integer(required=True, strict=True, validate=lambda value: value > 0)
    service_id = fields.Integer(required=True, strict=True, validate=lambda value: value > 0)
    start_at = fields.AwareDateTime(required=True)


class RescheduleAppointmentSchema(Schema):
    class Meta:
        unknown = RAISE

    start_at = fields.AwareDateTime(required=True)


class AppointmentListQuerySchema(Schema):
    class Meta:
        unknown = RAISE

    status = fields.String(validate=lambda value: value in {"scheduled", "cancelled"})
    page = fields.Integer(load_default=1, strict=True)
    per_page = fields.Integer(load_default=20, strict=True)

    @validates("page")
    def validate_page(self, value: int, **kwargs) -> None:
        if value < 1:
            raise ValidationError("page deve ser maior que zero.")

    @validates("per_page")
    def validate_per_page(self, value: int, **kwargs) -> None:
        if not 1 <= value <= 100:
            raise ValidationError("per_page deve estar entre 1 e 100.")

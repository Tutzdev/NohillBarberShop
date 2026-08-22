"""add availability domain

Revision ID: b8d2e9a1c4f0
Revises: f6b9ec95bfe8
Create Date: 2026-08-22 15:20:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "b8d2e9a1c4f0"
down_revision = "f6b9ec95bfe8"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "barbers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_barbers")),
    )
    op.create_table(
        "services",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("duration_minutes > 0", name=op.f("ck_services_positive_duration")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_services")),
    )
    op.create_table(
        "barber_services",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("barber_id", sa.Integer(), nullable=False),
        sa.Column("service_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["barber_id"], ["barbers.id"], name=op.f("fk_barber_services_barber_id_barbers")
        ),
        sa.ForeignKeyConstraint(
            ["service_id"], ["services.id"], name=op.f("fk_barber_services_service_id_services")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_barber_services")),
        sa.UniqueConstraint(
            "barber_id", "service_id", name=op.f("uq_barber_services_barber_service")
        ),
    )
    with op.batch_alter_table("barber_services") as batch_op:
        batch_op.create_index(batch_op.f("ix_barber_services_barber_id"), ["barber_id"])
        batch_op.create_index(batch_op.f("ix_barber_services_service_id"), ["service_id"])

    op.create_table(
        "working_hours",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("barber_id", sa.Integer(), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "weekday >= 0 AND weekday <= 6", name=op.f("ck_working_hours_valid_weekday")
        ),
        sa.CheckConstraint(
            "end_time > start_time", name=op.f("ck_working_hours_positive_interval")
        ),
        sa.ForeignKeyConstraint(
            ["barber_id"], ["barbers.id"], name=op.f("fk_working_hours_barber_id_barbers")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_working_hours")),
    )
    with op.batch_alter_table("working_hours") as batch_op:
        batch_op.create_index(batch_op.f("ix_working_hours_barber_id"), ["barber_id"])
        batch_op.create_index("ix_working_hours_barber_weekday", ["barber_id", "weekday"])

    op.create_table(
        "blocked_periods",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("barber_id", sa.Integer(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("end_at > start_at", name=op.f("ck_blocked_periods_positive_interval")),
        sa.ForeignKeyConstraint(
            ["barber_id"], ["barbers.id"], name=op.f("fk_blocked_periods_barber_id_barbers")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_blocked_periods")),
    )
    with op.batch_alter_table("blocked_periods") as batch_op:
        batch_op.create_index(batch_op.f("ix_blocked_periods_barber_id"), ["barber_id"])
        batch_op.create_index(
            "ix_blocked_periods_barber_start_end", ["barber_id", "start_at", "end_at"]
        )

    with op.batch_alter_table("appointments", recreate="always") as batch_op:
        batch_op.create_foreign_key(
            "fk_appointments_barber_id_barbers", "barbers", ["barber_id"], ["id"]
        )
        batch_op.create_foreign_key(
            "fk_appointments_service_id_services", "services", ["service_id"], ["id"]
        )


def downgrade():
    with op.batch_alter_table("appointments", recreate="always") as batch_op:
        batch_op.drop_constraint("fk_appointments_service_id_services", type_="foreignkey")
        batch_op.drop_constraint("fk_appointments_barber_id_barbers", type_="foreignkey")

    op.drop_table("blocked_periods")
    op.drop_table("working_hours")
    op.drop_table("barber_services")
    op.drop_table("services")
    op.drop_table("barbers")

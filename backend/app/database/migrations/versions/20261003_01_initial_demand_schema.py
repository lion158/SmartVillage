"""Create the initial stop and synthetic demand schema.

Revision ID: 20261003_01
Revises:
Create Date: 2026-10-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261003_01"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "stops",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "main_hub", "local", name="stop_kind", native_enum=False, create_constraint=True
            ),
            nullable=False,
        ),
        sa.Column(
            "source",
            sa.Enum(
                "synthetic",
                "osm",
                "manual",
                name="stop_source",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("source_reference", sa.String(length=200), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("latitude >= -90 AND latitude <= 90", name="ck_stops_latitude_range"),
        sa.CheckConstraint(
            "longitude >= -180 AND longitude <= 180", name="ck_stops_longitude_range"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_stops"),
    )
    op.create_index("ix_stops_kind_active", "stops", ["kind", "is_active"])
    op.create_index(
        "uq_stops_source_reference",
        "stops",
        ["source", "source_reference"],
        unique=True,
        sqlite_where=sa.text("source_reference IS NOT NULL"),
    )

    op.create_table(
        "simulation_scenarios",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("service_date", sa.Date(), nullable=False),
        sa.Column("main_hub_stop_id", sa.Integer(), nullable=False),
        sa.Column("planning_cutoff_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("random_seed", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "demand_ready",
                "planned",
                "completed",
                name="scenario_status",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="draft",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["main_hub_stop_id"],
            ["stops.id"],
            name="fk_simulation_scenarios_main_hub_stop_id_stops",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_simulation_scenarios"),
    )
    op.create_index(
        "ix_simulation_scenarios_date_status",
        "simulation_scenarios",
        ["service_date", "status"],
    )

    op.create_table(
        "passengers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scenario_id", sa.Integer(), nullable=False),
        sa.Column(
            "persona_type",
            sa.Enum(
                "student",
                "worker",
                "senior",
                "occasional",
                name="persona_type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("home_stop_id", sa.Integer(), nullable=False),
        sa.Column("reduced_mobility", sa.Boolean(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["home_stop_id"],
            ["stops.id"],
            name="fk_passengers_home_stop_id_stops",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["scenario_id"],
            ["simulation_scenarios.id"],
            name="fk_passengers_scenario_id_simulation_scenarios",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_passengers"),
    )
    op.create_index(
        "ix_passengers_scenario_home_stop", "passengers", ["scenario_id", "home_stop_id"]
    )
    op.create_index("ix_passengers_scenario_persona", "passengers", ["scenario_id", "persona_type"])

    op.create_table(
        "trip_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scenario_id", sa.Integer(), nullable=False),
        sa.Column("passenger_id", sa.Integer(), nullable=False),
        sa.Column("origin_stop_id", sa.Integer(), nullable=False),
        sa.Column("destination_stop_id", sa.Integer(), nullable=False),
        sa.Column(
            "trip_purpose",
            sa.Enum(
                "school",
                "work",
                "shopping",
                "healthcare",
                "leisure",
                "other",
                name="trip_purpose",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("desired_arrival_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("desired_departure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("passenger_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "request_source",
            sa.Enum(
                "planned", "late", name="request_source", native_enum=False, create_constraint=True
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "assigned",
                "rejected",
                "cancelled",
                name="request_status",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "origin_stop_id <> destination_stop_id", name="ck_trip_requests_different_stops"
        ),
        sa.CheckConstraint(
            "desired_arrival_at IS NOT NULL OR desired_departure_at IS NOT NULL",
            name="ck_trip_requests_desired_time_present",
        ),
        sa.CheckConstraint("passenger_count > 0", name="ck_trip_requests_positive_passenger_count"),
        sa.ForeignKeyConstraint(
            ["destination_stop_id"],
            ["stops.id"],
            name="fk_trip_requests_destination_stop_id_stops",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["origin_stop_id"],
            ["stops.id"],
            name="fk_trip_requests_origin_stop_id_stops",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["passenger_id"],
            ["passengers.id"],
            name="fk_trip_requests_passenger_id_passengers",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["scenario_id"],
            ["simulation_scenarios.id"],
            name="fk_trip_requests_scenario_id_simulation_scenarios",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_trip_requests"),
    )
    op.create_index("ix_trip_requests_passenger", "trip_requests", ["passenger_id"])
    op.create_index(
        "ix_trip_requests_scenario_status_arrival",
        "trip_requests",
        ["scenario_id", "status", "desired_arrival_at"],
    )
    op.create_index(
        "ix_trip_requests_stops",
        "trip_requests",
        ["origin_stop_id", "destination_stop_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_trip_requests_stops", table_name="trip_requests")
    op.drop_index("ix_trip_requests_scenario_status_arrival", table_name="trip_requests")
    op.drop_index("ix_trip_requests_passenger", table_name="trip_requests")
    op.drop_table("trip_requests")
    op.drop_index("ix_passengers_scenario_persona", table_name="passengers")
    op.drop_index("ix_passengers_scenario_home_stop", table_name="passengers")
    op.drop_table("passengers")
    op.drop_index("ix_simulation_scenarios_date_status", table_name="simulation_scenarios")
    op.drop_table("simulation_scenarios")
    op.drop_index("uq_stops_source_reference", table_name="stops")
    op.drop_index("ix_stops_kind_active", table_name="stops")
    op.drop_table("stops")

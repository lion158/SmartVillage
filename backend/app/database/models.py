"""Persistence models for stops and single-day synthetic demand."""

from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database.base import Base


def enum_type(enum_class: type[StrEnum], name: str) -> Enum:
    """Build a portable string-backed enum with database validation."""

    return Enum(
        enum_class,
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        values_callable=lambda members: [member.value for member in members],
    )


class StopKind(StrEnum):
    MAIN_HUB = "main_hub"
    LOCAL = "local"


class StopSource(StrEnum):
    SYNTHETIC = "synthetic"
    OSM = "osm"
    MANUAL = "manual"


class ScenarioStatus(StrEnum):
    DRAFT = "draft"
    DEMAND_READY = "demand_ready"
    PLANNED = "planned"
    COMPLETED = "completed"


class PersonaType(StrEnum):
    STUDENT = "student"
    WORKER = "worker"
    SENIOR = "senior"
    OCCASIONAL = "occasional"


class TripPurpose(StrEnum):
    SCHOOL = "school"
    WORK = "work"
    SHOPPING = "shopping"
    HEALTHCARE = "healthcare"
    LEISURE = "leisure"
    OTHER = "other"


class RequestSource(StrEnum):
    PLANNED = "planned"
    LATE = "late"


class RequestStatus(StrEnum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class Stop(Base):
    __tablename__ = "stops"
    __table_args__ = (
        CheckConstraint("latitude >= -90 AND latitude <= 90", name="latitude_range"),
        CheckConstraint("longitude >= -180 AND longitude <= 180", name="longitude_range"),
        Index("ix_stops_kind_active", "kind", "is_active"),
        Index("ix_stops_locality_kind", "locality", "kind"),
        Index(
            "uq_stops_source_reference",
            "source",
            "source_reference",
            unique=True,
            sqlite_where=text("source_reference IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    locality: Mapped[str] = mapped_column(String(120))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    kind: Mapped[StopKind] = mapped_column(enum_type(StopKind, "stop_kind"))
    source: Mapped[StopSource] = mapped_column(enum_type(StopSource, "stop_source"))
    source_reference: Mapped[str | None] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.current_timestamp()
    )


class SimulationScenario(Base):
    __tablename__ = "simulation_scenarios"
    __table_args__ = (Index("ix_simulation_scenarios_date_status", "service_date", "status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    service_date: Mapped[date] = mapped_column(Date)
    main_hub_stop_id: Mapped[int] = mapped_column(ForeignKey("stops.id", ondelete="RESTRICT"))
    planning_cutoff_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    random_seed: Mapped[int] = mapped_column(Integer)
    status: Mapped[ScenarioStatus] = mapped_column(
        enum_type(ScenarioStatus, "scenario_status"),
        default=ScenarioStatus.DRAFT,
        server_default=ScenarioStatus.DRAFT.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.current_timestamp()
    )

    main_hub: Mapped[Stop] = relationship(foreign_keys=[main_hub_stop_id])
    passengers: Mapped[list["Passenger"]] = relationship(
        back_populates="scenario", cascade="all, delete-orphan"
    )
    trip_requests: Mapped[list["TripRequest"]] = relationship(
        back_populates="scenario", cascade="all, delete-orphan"
    )


class Passenger(Base):
    __tablename__ = "passengers"
    __table_args__ = (
        Index("ix_passengers_scenario_persona", "scenario_id", "persona_type"),
        Index("ix_passengers_scenario_home_stop", "scenario_id", "home_stop_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    scenario_id: Mapped[int] = mapped_column(
        ForeignKey("simulation_scenarios.id", ondelete="CASCADE")
    )
    persona_type: Mapped[PersonaType] = mapped_column(enum_type(PersonaType, "persona_type"))
    home_stop_id: Mapped[int] = mapped_column(ForeignKey("stops.id", ondelete="RESTRICT"))
    reduced_mobility: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.current_timestamp()
    )

    scenario: Mapped[SimulationScenario] = relationship(back_populates="passengers")
    home_stop: Mapped[Stop] = relationship(foreign_keys=[home_stop_id])
    trip_requests: Mapped[list["TripRequest"]] = relationship(
        back_populates="passenger", cascade="all, delete-orphan"
    )


class TripRequest(Base):
    __tablename__ = "trip_requests"
    __table_args__ = (
        CheckConstraint("origin_stop_id <> destination_stop_id", name="different_stops"),
        CheckConstraint(
            "desired_arrival_at IS NOT NULL OR desired_departure_at IS NOT NULL",
            name="desired_time_present",
        ),
        CheckConstraint("passenger_count > 0", name="positive_passenger_count"),
        Index(
            "ix_trip_requests_scenario_status_arrival",
            "scenario_id",
            "status",
            "desired_arrival_at",
        ),
        Index("ix_trip_requests_stops", "origin_stop_id", "destination_stop_id"),
        Index("ix_trip_requests_passenger", "passenger_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    scenario_id: Mapped[int] = mapped_column(
        ForeignKey("simulation_scenarios.id", ondelete="CASCADE")
    )
    passenger_id: Mapped[int] = mapped_column(ForeignKey("passengers.id", ondelete="CASCADE"))
    origin_stop_id: Mapped[int] = mapped_column(ForeignKey("stops.id", ondelete="RESTRICT"))
    destination_stop_id: Mapped[int] = mapped_column(ForeignKey("stops.id", ondelete="RESTRICT"))
    trip_purpose: Mapped[TripPurpose] = mapped_column(enum_type(TripPurpose, "trip_purpose"))
    desired_arrival_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    desired_departure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    passenger_count: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    request_source: Mapped[RequestSource] = mapped_column(
        enum_type(RequestSource, "request_source")
    )
    status: Mapped[RequestStatus] = mapped_column(
        enum_type(RequestStatus, "request_status"),
        default=RequestStatus.PENDING,
        server_default=RequestStatus.PENDING.value,
    )
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    scenario: Mapped[SimulationScenario] = relationship(back_populates="trip_requests")
    passenger: Mapped[Passenger] = relationship(back_populates="trip_requests")
    origin_stop: Mapped[Stop] = relationship(foreign_keys=[origin_stop_id])
    destination_stop: Mapped[Stop] = relationship(foreign_keys=[destination_stop_id])

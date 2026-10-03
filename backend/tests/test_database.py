from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.base import Base
from app.database.models import (
    Passenger,
    PersonaType,
    RequestSource,
    SimulationScenario,
    Stop,
    StopKind,
    StopSource,
    TripPurpose,
    TripRequest,
)
from app.database.seeds.stops import DESTINATION_STOPS, LOCAL_STOPS, STOP_SEEDS, seed_stops
from app.database.session import create_database_engine
from app.database.stops_map import build_stops_map


def test_single_day_demand_can_be_persisted(tmp_path) -> None:
    database_path = tmp_path / "test.db"
    engine = create_database_engine(f"sqlite:///{database_path}")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        hub = Stop(
            name="Klodzko main hub",
            locality="Klodzko",
            latitude=50.437,
            longitude=16.652,
            kind=StopKind.MAIN_HUB,
            source=StopSource.MANUAL,
        )
        local_stop = Stop(
            name="Synthetic stop 1",
            locality="Synthetic village",
            latitude=50.443,
            longitude=16.65,
            kind=StopKind.LOCAL,
            source=StopSource.SYNTHETIC,
            source_reference="synthetic-1",
        )
        session.add_all([hub, local_stop])
        session.flush()

        scenario = SimulationScenario(
            name="Typical Monday",
            service_date=date(2026, 10, 5),
            main_hub_stop_id=hub.id,
            planning_cutoff_at=datetime(2026, 10, 4, 20, tzinfo=UTC),
            random_seed=12345,
        )
        session.add(scenario)
        session.flush()

        passenger = Passenger(
            scenario_id=scenario.id,
            persona_type=PersonaType.STUDENT,
            home_stop_id=local_stop.id,
        )
        session.add(passenger)
        session.flush()

        request = TripRequest(
            scenario_id=scenario.id,
            passenger_id=passenger.id,
            origin_stop_id=local_stop.id,
            destination_stop_id=hub.id,
            trip_purpose=TripPurpose.SCHOOL,
            desired_arrival_at=datetime(2026, 10, 5, 5, 45, tzinfo=UTC),
            request_source=RequestSource.PLANNED,
            submitted_at=datetime(2026, 10, 4, 18, 30, tzinfo=UTC),
        )
        session.add(request)
        session.commit()

    with Session(engine) as session:
        stored_request = session.scalar(select(TripRequest))

        assert stored_request is not None
        assert stored_request.passenger.persona_type == PersonaType.STUDENT
        assert stored_request.origin_stop.name == "Synthetic stop 1"
        assert stored_request.destination_stop.kind == StopKind.MAIN_HUB


def test_sqlite_foreign_keys_are_enabled(tmp_path) -> None:
    engine = create_database_engine(f"sqlite:///{tmp_path / 'test.db'}")

    with engine.connect() as connection:
        enabled = connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one()

    assert enabled == 1


def test_stop_seed_is_complete_and_idempotent(tmp_path) -> None:
    engine = create_database_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        assert seed_stops(session) == (len(STOP_SEEDS), 0)
        session.commit()

        assert seed_stops(session) == (0, len(STOP_SEEDS))
        session.commit()

        stop_count = session.scalar(select(func.count()).select_from(Stop))

    assert stop_count == len(STOP_SEEDS)
    assert len(DESTINATION_STOPS) == 9
    assert len(LOCAL_STOPS) == 32


def test_stop_map_contains_seeded_stops(tmp_path) -> None:
    engine = create_database_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        seed_stops(session)
        session.commit()
        output_path = build_stops_map(session, tmp_path / "stops_map.html")

    map_html = output_path.read_text(encoding="utf-8")
    assert "Kłodzko Miasto" in map_html
    assert "Jaszkowa Dolna nż" in map_html
    assert "Destination stops" in map_html
    assert "Local pickup stops" in map_html

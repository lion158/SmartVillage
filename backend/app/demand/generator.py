"""Generate reproducible passengers and inbound demand for one service day."""

import argparse
import math
import random
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import (
    Passenger,
    PersonaType,
    RequestSource,
    ScenarioStatus,
    SimulationScenario,
    Stop,
    StopKind,
    TripPurpose,
    TripRequest,
)
from app.database.session import SessionLocal

LOCAL_TIME_ZONE = ZoneInfo("Europe/Warsaw")

PERSONA_WEIGHTS = {
    PersonaType.STUDENT: 0.30,
    PersonaType.WORKER: 0.40,
    PersonaType.SENIOR: 0.20,
    PersonaType.OCCASIONAL: 0.10,
}

PURPOSE_WEIGHTS = {
    PersonaType.STUDENT: {
        TripPurpose.SCHOOL: 0.90,
        TripPurpose.OTHER: 0.10,
    },
    PersonaType.WORKER: {
        TripPurpose.WORK: 0.90,
        TripPurpose.SHOPPING: 0.10,
    },
    PersonaType.SENIOR: {
        TripPurpose.SHOPPING: 0.45,
        TripPurpose.HEALTHCARE: 0.40,
        TripPurpose.LEISURE: 0.15,
    },
    PersonaType.OCCASIONAL: {
        TripPurpose.SHOPPING: 0.35,
        TripPurpose.LEISURE: 0.35,
        TripPurpose.HEALTHCARE: 0.15,
        TripPurpose.OTHER: 0.15,
    },
}

REDUCED_MOBILITY_PROBABILITY = {
    PersonaType.STUDENT: 0.01,
    PersonaType.WORKER: 0.02,
    PersonaType.SENIOR: 0.30,
    PersonaType.OCCASIONAL: 0.03,
}

# Mean minute of day, standard deviation, earliest minute, latest minute.
ARRIVAL_PROFILES = {
    TripPurpose.SCHOOL: (7 * 60 + 45, 15, 7 * 60, 8 * 60 + 30),
    TripPurpose.WORK: (8 * 60, 40, 6 * 60, 9 * 60 + 30),
    TripPurpose.SHOPPING: (10 * 60 + 30, 60, 8 * 60 + 30, 14 * 60),
    TripPurpose.HEALTHCARE: (9 * 60 + 30, 60, 7 * 60 + 30, 13 * 60),
    TripPurpose.LEISURE: (13 * 60, 120, 9 * 60, 18 * 60),
    TripPurpose.OTHER: (11 * 60, 120, 7 * 60, 18 * 60),
}

CITY_ATTRACTIVENESS = {
    "Kłodzko": 1.6,
    "Bystrzyca Kłodzka": 1.0,
    "Polanica-Zdrój": 1.0,
}
NON_NEAREST_CITY_PROBABILITY = 0.25


@dataclass(frozen=True)
class DemandGenerationConfig:
    service_date: date
    passenger_count: int = 1000
    random_seed: int = 42
    name: str | None = None
    planning_cutoff_hour: int = 20


@dataclass(frozen=True)
class DemandGenerationSummary:
    scenario_id: int
    passenger_count: int
    persona_counts: dict[str, int]
    purpose_counts: dict[str, int]
    destination_counts: dict[str, int]


def generate_demand(session: Session, config: DemandGenerationConfig) -> DemandGenerationSummary:
    """Generate one complete, reproducible inbound-demand scenario."""

    _validate_config(config)
    local_stops = session.scalars(
        select(Stop).where(Stop.kind == StopKind.LOCAL, Stop.is_active.is_(True)).order_by(Stop.id)
    ).all()
    destination_stops = session.scalars(
        select(Stop)
        .where(Stop.kind == StopKind.MAIN_HUB, Stop.is_active.is_(True))
        .order_by(Stop.id)
    ).all()
    if not local_stops:
        raise ValueError("No active local stops found. Run the stop seed command first.")
    if not destination_stops:
        raise ValueError("No active destination stops found. Run the stop seed command first.")

    default_hub = next(
        (stop for stop in destination_stops if stop.name == "Kłodzko Miasto"),
        destination_stops[0],
    )
    cutoff_local = datetime.combine(
        config.service_date - timedelta(days=1),
        time(config.planning_cutoff_hour),
        tzinfo=LOCAL_TIME_ZONE,
    )
    scenario = SimulationScenario(
        name=config.name
        or f"Synthetic demand {config.service_date.isoformat()} seed {config.random_seed}",
        service_date=config.service_date,
        main_hub_stop_id=default_hub.id,
        planning_cutoff_at=cutoff_local.astimezone(UTC),
        random_seed=config.random_seed,
        status=ScenarioStatus.DRAFT,
    )
    session.add(scenario)
    session.flush()

    rng = random.Random(config.random_seed)
    persona_counts: Counter[str] = Counter()
    purpose_counts: Counter[str] = Counter()
    destination_counts: Counter[str] = Counter()

    for _ in range(config.passenger_count):
        persona = _weighted_choice(rng, PERSONA_WEIGHTS)
        purpose = _weighted_choice(rng, PURPOSE_WEIGHTS[persona])
        origin = rng.choice(local_stops)
        destination = _choose_destination(rng, origin, destination_stops, purpose)
        passenger = Passenger(
            scenario=scenario,
            persona_type=persona,
            home_stop=origin,
            reduced_mobility=rng.random() < REDUCED_MOBILITY_PROBABILITY[persona],
        )
        request = TripRequest(
            scenario=scenario,
            passenger=passenger,
            origin_stop=origin,
            destination_stop=destination,
            trip_purpose=purpose,
            desired_arrival_at=_generate_arrival_time(rng, config.service_date, purpose),
            desired_departure_at=None,
            passenger_count=1,
            request_source=RequestSource.PLANNED,
            submitted_at=_generate_submission_time(rng, cutoff_local),
        )
        session.add(request)
        persona_counts[persona.value] += 1
        purpose_counts[purpose.value] += 1
        destination_counts[destination.locality] += 1

    scenario.status = ScenarioStatus.DEMAND_READY
    session.flush()
    return DemandGenerationSummary(
        scenario_id=scenario.id,
        passenger_count=config.passenger_count,
        persona_counts=dict(sorted(persona_counts.items())),
        purpose_counts=dict(sorted(purpose_counts.items())),
        destination_counts=dict(sorted(destination_counts.items())),
    )


def _validate_config(config: DemandGenerationConfig) -> None:
    if config.passenger_count <= 0:
        raise ValueError("Passenger count must be greater than zero.")
    if not 8 <= config.planning_cutoff_hour <= 23:
        raise ValueError("Planning cutoff hour must be between 8 and 23.")


def _weighted_choice(rng: random.Random, weights: dict):
    values = list(weights)
    return rng.choices(values, weights=[weights[value] for value in values], k=1)[0]


def _choose_destination(
    rng: random.Random,
    origin: Stop,
    destination_stops: list[Stop],
    purpose: TripPurpose,
) -> Stop:
    stops_by_city: dict[str, list[Stop]] = {}
    for stop in destination_stops:
        stops_by_city.setdefault(stop.locality, []).append(stop)

    cities = list(stops_by_city)
    distances = {}
    for city in cities:
        city_stops = stops_by_city[city]
        center_latitude = sum(stop.latitude for stop in city_stops) / len(city_stops)
        center_longitude = sum(stop.longitude for stop in city_stops) / len(city_stops)
        distance = max(
            _distance_km(
                origin.latitude,
                origin.longitude,
                center_latitude,
                center_longitude,
            ),
            1.0,
        )
        distances[city] = distance

    nearest_city = min(cities, key=lambda city: distances[city])
    if len(cities) > 1 and rng.random() < NON_NEAREST_CITY_PROBABILITY:
        selectable_cities = [city for city in cities if city != nearest_city]
        selected_city = rng.choices(
            selectable_cities,
            weights=[
                CITY_ATTRACTIVENESS.get(city, 1.0) / distances[city] ** 0.7
                for city in selectable_cities
            ],
            k=1,
        )[0]
    else:
        selected_city = nearest_city
    candidates = stops_by_city[selected_city]
    if purpose == TripPurpose.HEALTHCARE:
        hospital = next((stop for stop in candidates if "Szpital" in stop.name), None)
        if hospital is not None and rng.random() < 0.75:
            return hospital
    return rng.choice(candidates)


def _generate_arrival_time(
    rng: random.Random, service_date: date, purpose: TripPurpose
) -> datetime:
    mean, standard_deviation, earliest, latest = ARRIVAL_PROFILES[purpose]
    minute = round(rng.gauss(mean, standard_deviation))
    minute = min(max(minute, earliest), latest)
    local_arrival = datetime.combine(service_date, time.min, tzinfo=LOCAL_TIME_ZONE) + timedelta(
        minutes=minute
    )
    return local_arrival.astimezone(UTC)


def _generate_submission_time(rng: random.Random, cutoff_local: datetime) -> datetime:
    submission_start = datetime.combine(cutoff_local.date(), time(8), tzinfo=LOCAL_TIME_ZONE)
    available_seconds = int((cutoff_local - submission_start).total_seconds())
    submitted_local = submission_start + timedelta(seconds=rng.randint(0, available_seconds))
    return submitted_local.astimezone(UTC)


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    earth_radius_km = 6371.0
    latitude_delta = math.radians(lat2 - lat1)
    longitude_delta = math.radians(lon2 - lon1)
    a = (
        math.sin(latitude_delta / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(longitude_delta / 2) ** 2
    )
    return earth_radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("Date must use YYYY-MM-DD format.") from error


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True, type=_parse_date, help="Service date (YYYY-MM-DD)")
    parser.add_argument("--passengers", type=int, default=1000, help="Number of passengers")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic random seed")
    parser.add_argument("--name", help="Optional scenario name")
    args = parser.parse_args()

    config = DemandGenerationConfig(
        service_date=args.date,
        passenger_count=args.passengers,
        random_seed=args.seed,
        name=args.name,
    )
    with SessionLocal.begin() as session:
        summary = generate_demand(session, config)

    print(f"Scenario {summary.scenario_id} is ready with {summary.passenger_count} passengers.")
    print(f"Personas: {summary.persona_counts}")
    print(f"Purposes: {summary.purpose_counts}")
    print(f"Destinations: {summary.destination_counts}")


if __name__ == "__main__":
    main()

"""Generate an interactive HTML report for a synthetic demand scenario."""

import argparse
import html
import math
from collections import Counter, defaultdict
from datetime import UTC
from pathlib import Path

import folium
from folium.plugins import HeatMap
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database.models import SimulationScenario, Stop, StopKind, TripRequest
from app.database.session import BACKEND_DIR, SessionLocal
from app.demand.generator import LOCAL_TIME_ZONE, _distance_km

PERSONA_COLORS = {
    "student": "#7e57c2",
    "worker": "#1976d2",
    "senior": "#ef6c00",
    "occasional": "#00897b",
}
DESTINATION_COLORS = {
    "Kłodzko": "#c62828",
    "Bystrzyca Kłodzka": "#ad1457",
    "Polanica-Zdrój": "#6a1b9a",
}


def build_demand_report(session: Session, scenario_id: int, output_path: Path) -> Path:
    """Build an interactive map and summary dashboard for one scenario."""

    scenario = session.get(SimulationScenario, scenario_id)
    if scenario is None:
        raise ValueError(f"Scenario {scenario_id} does not exist.")

    requests = session.scalars(
        select(TripRequest)
        .where(TripRequest.scenario_id == scenario_id)
        .options(
            selectinload(TripRequest.passenger),
            selectinload(TripRequest.origin_stop),
            selectinload(TripRequest.destination_stop),
        )
        .order_by(TripRequest.id)
    ).all()
    if not requests:
        raise ValueError(f"Scenario {scenario_id} has no trip requests.")

    destination_stops = session.scalars(
        select(Stop).where(Stop.kind == StopKind.MAIN_HUB).order_by(Stop.id)
    ).all()
    city_centers = _city_centers(destination_stops)
    persona_counts = Counter(request.passenger.persona_type.value for request in requests)
    purpose_counts = Counter(request.trip_purpose.value for request in requests)
    destination_city_counts = Counter(request.destination_stop.locality for request in requests)
    destination_stop_counts = Counter(request.destination_stop_id for request in requests)
    origin_counts = Counter(request.origin_stop_id for request in requests)
    arrival_hour_counts = Counter(_local_arrival_hour(request) for request in requests)
    non_nearest_count = sum(
        request.destination_stop.locality != _nearest_city(request.origin_stop, city_centers)
        for request in requests
    )

    stops_by_id = {
        stop.id: stop
        for request in requests
        for stop in (request.origin_stop, request.destination_stop)
    }
    map_center = [
        sum(stop.latitude for stop in stops_by_id.values()) / len(stops_by_id),
        sum(stop.longitude for stop in stops_by_id.values()) / len(stops_by_id),
    ]
    demand_map = folium.Map(
        location=map_center,
        tiles="OpenStreetMap",
        zoom_start=10,
        control_scale=True,
    )

    origin_layer = folium.FeatureGroup(name="Passenger origins", show=True)
    destination_layer = folium.FeatureGroup(name="Destination stops", show=True)
    flow_layer = folium.FeatureGroup(name="Aggregated flows", show=False)
    heat_layer = folium.FeatureGroup(name="Demand heatmap", show=False)

    origin_requests: dict[int, list[TripRequest]] = defaultdict(list)
    for request in requests:
        origin_requests[request.origin_stop_id].append(request)

    for stop_id, stop_requests in origin_requests.items():
        stop = stops_by_id[stop_id]
        count = len(stop_requests)
        personas = Counter(request.passenger.persona_type.value for request in stop_requests)
        destinations = Counter(request.destination_stop.locality for request in stop_requests)
        popup = folium.Popup(
            _stop_popup(stop, count, personas, destinations),
            max_width=360,
        )
        folium.CircleMarker(
            location=[stop.latitude, stop.longitude],
            radius=5 + math.sqrt(count) * 1.5,
            color="#0d47a1",
            fill=True,
            fill_color="#1976d2",
            fill_opacity=0.75,
            weight=2,
            tooltip=f"{stop.name}: {count} passengers",
            popup=popup,
        ).add_to(origin_layer)

    for stop_id, count in destination_stop_counts.items():
        stop = stops_by_id[stop_id]
        folium.CircleMarker(
            location=[stop.latitude, stop.longitude],
            radius=7 + math.sqrt(count) * 0.8,
            color="#8e0000",
            fill=True,
            fill_color="#d32f2f",
            fill_opacity=0.85,
            weight=2,
            tooltip=f"{stop.name}: {count} arrivals",
            popup=folium.Popup(
                f"<strong>{html.escape(stop.name)}</strong><br>Arrivals: {count}",
                max_width=300,
            ),
        ).add_to(destination_layer)

    flow_counts = Counter(
        (request.origin_stop_id, request.destination_stop.locality) for request in requests
    )
    for (origin_stop_id, destination_city), count in flow_counts.items():
        origin = stops_by_id[origin_stop_id]
        city_latitude, city_longitude = city_centers[destination_city]
        folium.PolyLine(
            locations=[
                [origin.latitude, origin.longitude],
                [city_latitude, city_longitude],
            ],
            color="#455a64",
            weight=min(1 + count / 4, 8),
            opacity=0.3,
            tooltip=f"{origin.locality} → {destination_city}: {count}",
        ).add_to(flow_layer)

    HeatMap(
        [
            [stops_by_id[stop_id].latitude, stops_by_id[stop_id].longitude, count]
            for stop_id, count in origin_counts.items()
        ],
        radius=25,
        blur=18,
        min_opacity=0.35,
    ).add_to(heat_layer)

    origin_layer.add_to(demand_map)
    destination_layer.add_to(demand_map)
    flow_layer.add_to(demand_map)
    heat_layer.add_to(demand_map)
    folium.LayerControl(collapsed=False).add_to(demand_map)
    demand_map.fit_bounds(
        [
            [
                min(stop.latitude for stop in stops_by_id.values()),
                min(stop.longitude for stop in stops_by_id.values()),
            ],
            [
                max(stop.latitude for stop in stops_by_id.values()),
                max(stop.longitude for stop in stops_by_id.values()),
            ],
        ],
        padding=(30, 30),
    )

    dashboard = _dashboard_html(
        scenario,
        len(requests),
        persona_counts,
        purpose_counts,
        destination_city_counts,
        arrival_hour_counts,
        origin_counts,
        stops_by_id,
        non_nearest_count,
    )
    demand_map.get_root().html.add_child(folium.Element(dashboard))

    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    demand_map.save(output_path)
    return output_path


def _city_centers(stops: list[Stop]) -> dict[str, tuple[float, float]]:
    grouped: dict[str, list[Stop]] = defaultdict(list)
    for stop in stops:
        grouped[stop.locality].append(stop)
    return {
        city: (
            sum(stop.latitude for stop in city_stops) / len(city_stops),
            sum(stop.longitude for stop in city_stops) / len(city_stops),
        )
        for city, city_stops in grouped.items()
    }


def _nearest_city(origin: Stop, city_centers: dict[str, tuple[float, float]]) -> str:
    return min(
        city_centers,
        key=lambda city: _distance_km(
            origin.latitude,
            origin.longitude,
            *city_centers[city],
        ),
    )


def _local_arrival_hour(request: TripRequest) -> int:
    arrival = request.desired_arrival_at
    if arrival is None:
        return 0
    if arrival.tzinfo is None:
        arrival = arrival.replace(tzinfo=UTC)
    return arrival.astimezone(LOCAL_TIME_ZONE).hour


def _stop_popup(
    stop: Stop,
    count: int,
    personas: Counter[str],
    destinations: Counter[str],
) -> str:
    persona_text = ", ".join(f"{name}: {value}" for name, value in personas.most_common())
    destination_text = ", ".join(f"{name}: {value}" for name, value in destinations.most_common())
    return (
        f"<strong>{html.escape(stop.name)}</strong><br>"
        f"Locality: {html.escape(stop.locality)}<br>"
        f"Passengers: {count}<br>"
        f"Personas: {html.escape(persona_text)}<br>"
        f"Destinations: {html.escape(destination_text)}"
    )


def _dashboard_html(
    scenario: SimulationScenario,
    request_count: int,
    persona_counts: Counter[str],
    purpose_counts: Counter[str],
    destination_counts: Counter[str],
    arrival_counts: Counter[int],
    origin_counts: Counter[int],
    stops_by_id: dict[int, Stop],
    non_nearest_count: int,
) -> str:
    top_origins = Counter(
        {stops_by_id[stop_id].name: count for stop_id, count in origin_counts.items()}
    )
    persona_section = _bar_section("Personas", persona_counts, PERSONA_COLORS)
    purpose_section = _bar_section("Trip purposes", purpose_counts)
    destination_section = _bar_section("Destination cities", destination_counts, DESTINATION_COLORS)
    arrival_section = _bar_section(
        "Arrival hour",
        Counter({f"{hour:02d}:00": arrival_counts[hour] for hour in range(6, 19)}),
    )
    origin_section = _bar_section("Busiest origin stops", Counter(dict(top_origins.most_common(8))))
    return f"""
    <div class="demand-dashboard">
      <div class="dashboard-header">
        <div>
          <h2>{html.escape(scenario.name)}</h2>
          <p>{scenario.service_date.isoformat()} · scenario #{scenario.id}</p>
        </div>
        <button onclick="this.closest('.demand-dashboard').classList.toggle('collapsed')">⇔</button>
      </div>
      <div class="dashboard-content">
        <div class="metric-grid">
          <div class="metric">
            <strong>{request_count}</strong><span>passengers</span>
          </div>
          <div class="metric">
            <strong>{len(origin_counts)}</strong><span>origin stops</span>
          </div>
          <div class="metric">
            <strong>{non_nearest_count / request_count:.1%}</strong>
            <span>non-nearest city</span>
          </div>
        </div>
        {persona_section}
        {purpose_section}
        {destination_section}
        {arrival_section}
        {origin_section}
      </div>
    </div>
    <style>
      .demand-dashboard {{
        position: fixed; z-index: 9999; top: 12px; left: 12px;
        width: 360px; max-height: calc(100vh - 24px); overflow: auto;
        background: rgba(255,255,255,.96); border-radius: 12px;
        box-shadow: 0 5px 22px rgba(0,0,0,.28);
        font: 13px/1.3 Arial,sans-serif;
      }}
      .dashboard-header {{
        display:flex; justify-content:space-between; gap:10px;
        padding:14px 16px; background:#263238; color:white;
        border-radius:12px 12px 0 0;
      }}
      .dashboard-header h2 {{ font-size:16px; margin:0 0 3px; }}
      .dashboard-header p {{ margin:0; color:#cfd8dc; }}
      .dashboard-header button {{ border:0; border-radius:6px; cursor:pointer; height:28px; }}
      .dashboard-content {{ padding:12px 16px 16px; }}
      .collapsed .dashboard-content {{ display:none; }}
      .metric-grid {{
        display:grid; grid-template-columns:repeat(3,1fr);
        gap:7px; margin-bottom:14px;
      }}
      .metric {{ background:#eceff1; padding:8px 5px; text-align:center; border-radius:7px; }}
      .metric strong {{ display:block; font-size:18px; color:#263238; }}
      .metric span {{ color:#546e7a; font-size:10px; }}
      .bar-section {{ margin-top:12px; }}
      .bar-section h3 {{ margin:0 0 5px; font-size:12px; text-transform:uppercase; color:#455a64; }}
      .bar-row {{
        display:grid; grid-template-columns:115px 1fr 32px;
        gap:6px; align-items:center; margin:3px 0;
      }}
      .bar-label {{ white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
      .bar-track {{ height:9px; background:#eceff1; border-radius:6px; overflow:hidden; }}
      .bar-fill {{ height:100%; border-radius:6px; }}
      .bar-value {{ text-align:right; font-variant-numeric:tabular-nums; }}
      @media (max-width: 650px) {{
        .demand-dashboard {{ width:calc(100vw - 24px); max-height:45vh; }}
      }}
    </style>
    """


def _bar_section(
    title: str,
    counts: Counter,
    colors: dict[str, str] | None = None,
) -> str:
    maximum = max(counts.values(), default=1)
    rows = []
    for index, (label, value) in enumerate(counts.most_common()):
        color = (colors or {}).get(str(label), "#1976d2")
        width = value / maximum * 100
        rows.append(
            f'<div class="bar-row"><span class="bar-label" title="{html.escape(str(label))}">'
            f'{html.escape(str(label))}</span><div class="bar-track"><div class="bar-fill" '
            f'style="width:{width:.1f}%;background:{color}"></div></div>'
            f'<span class="bar-value">{value}</span></div>'
        )
    return f'<div class="bar-section"><h3>{html.escape(title)}</h3>{"".join(rows)}</div>'


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", required=True, type=int, help="Scenario identifier")
    parser.add_argument("--output", type=Path, help="Optional output HTML path")
    args = parser.parse_args()

    output_path = args.output or BACKEND_DIR / "data" / f"demand_scenario_{args.scenario}.html"
    with SessionLocal() as session:
        generated_path = build_demand_report(session, args.scenario, output_path)
    print(f"Demand report written to {generated_path}")


if __name__ == "__main__":
    main()

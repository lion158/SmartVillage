"""Generate an interactive HTML map from stops stored in the database."""

import html
from pathlib import Path

import folium
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Stop, StopKind
from app.database.session import BACKEND_DIR, SessionLocal

DEFAULT_MAP_PATH = BACKEND_DIR / "data" / "stops_map.html"


def build_stops_map(session: Session, output_path: Path = DEFAULT_MAP_PATH) -> Path:
    """Write an interactive stop map and return its resolved path."""

    stops = session.scalars(
        select(Stop).where(Stop.is_active.is_(True)).order_by(Stop.kind, Stop.locality, Stop.name)
    ).all()
    if not stops:
        raise ValueError("No active stops found. Run the stop seed command first.")

    center = [
        sum(stop.latitude for stop in stops) / len(stops),
        sum(stop.longitude for stop in stops) / len(stops),
    ]
    stop_map = folium.Map(location=center, tiles="OpenStreetMap", zoom_start=10, control_scale=True)

    destination_layer = folium.FeatureGroup(name="Destination stops", show=True)
    local_layer = folium.FeatureGroup(name="Local pickup stops", show=True)

    for stop in stops:
        is_destination = stop.kind == StopKind.MAIN_HUB
        color = "#c62828" if is_destination else "#1565c0"
        layer = destination_layer if is_destination else local_layer
        kind_label = "Destination" if is_destination else "Local pickup"
        osm_url = _osm_url(stop)
        source_link = (
            f'<a href="{html.escape(osm_url)}" target="_blank" rel="noopener">OpenStreetMap</a>'
            if osm_url
            else html.escape(stop.source.value)
        )
        popup = folium.Popup(
            (
                f"<strong>{html.escape(stop.name)}</strong><br>"
                f"Locality: {html.escape(stop.locality)}<br>"
                f"Type: {kind_label}<br>"
                f"Coordinates: {stop.latitude:.7f}, {stop.longitude:.7f}<br>"
                f"Source: {source_link}"
            ),
            max_width=320,
        )
        folium.CircleMarker(
            location=[stop.latitude, stop.longitude],
            radius=7 if is_destination else 5,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.9,
            weight=2,
            tooltip=f"{stop.name} ({kind_label})",
            popup=popup,
        ).add_to(layer)

    destination_layer.add_to(stop_map)
    local_layer.add_to(stop_map)
    folium.LayerControl(collapsed=False).add_to(stop_map)
    stop_map.fit_bounds(
        [
            [min(stop.latitude for stop in stops), min(stop.longitude for stop in stops)],
            [max(stop.latitude for stop in stops), max(stop.longitude for stop in stops)],
        ],
        padding=(30, 30),
    )

    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    stop_map.save(output_path)
    return output_path


def _osm_url(stop: Stop) -> str | None:
    if stop.source_reference is None or "/" not in stop.source_reference:
        return None

    object_type, object_id = stop.source_reference.split("/", maxsplit=1)
    if object_type not in {"node", "way", "relation"} or not object_id.isdigit():
        return None
    return f"https://www.openstreetmap.org/{object_type}/{object_id}"


def main() -> None:
    with SessionLocal() as session:
        output_path = build_stops_map(session)
    print(f"Stop map written to {output_path}")


if __name__ == "__main__":
    main()

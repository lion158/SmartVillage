"""Seed a curated set of bus stops for the Kłodzko area.

Coordinates and source identifiers are derived from OpenStreetMap data.
Copyright OpenStreetMap contributors, available under the ODbL.
https://www.openstreetmap.org/copyright
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Stop, StopKind, StopSource
from app.database.session import SessionLocal


@dataclass(frozen=True)
class StopSeed:
    name: str
    locality: str
    latitude: float
    longitude: float
    kind: StopKind
    osm_node_id: int

    @property
    def source_reference(self) -> str:
        return f"node/{self.osm_node_id}"


DESTINATION_STOPS = (
    StopSeed(
        "Kłodzko Miasto",
        "Kłodzko",
        50.4357611,
        16.6573008,
        StopKind.MAIN_HUB,
        10150932732,
    ),
    StopSeed(
        "Kłodzko Targowisko",
        "Kłodzko",
        50.4371862,
        16.6484943,
        StopKind.MAIN_HUB,
        2278078377,
    ),
    StopSeed(
        "Kłodzko, ul. Dusznicka",
        "Kłodzko",
        50.4395506,
        16.6373673,
        StopKind.MAIN_HUB,
        5921399943,
    ),
    StopSeed(
        "Kłodzko, Szpital - Pętla",
        "Kłodzko",
        50.4548725,
        16.6595960,
        StopKind.MAIN_HUB,
        9442286024,
    ),
    StopSeed(
        "Bystrzyca Kłodzka - Centrum",
        "Bystrzyca Kłodzka",
        50.2998428,
        16.6504232,
        StopKind.MAIN_HUB,
        13384259443,
    ),
    StopSeed(
        "Bystrzyca Kłodzka, ul. Wojska Polskiego",
        "Bystrzyca Kłodzka",
        50.3032839,
        16.6372979,
        StopKind.MAIN_HUB,
        13384259458,
    ),
    StopSeed(
        "Polanica-Zdrój, Warszawska/Dworcowa",
        "Polanica-Zdrój",
        50.3984317,
        16.5166303,
        StopKind.MAIN_HUB,
        9442596220,
    ),
    StopSeed(
        "Polanica-Zdrój, Zdrojowa/Leśna",
        "Polanica-Zdrój",
        50.4138622,
        16.5106671,
        StopKind.MAIN_HUB,
        7819393554,
    ),
    StopSeed(
        "Polanica-Zdrój, al. Wojska Polskiego",
        "Polanica-Zdrój",
        50.3985957,
        16.5043698,
        StopKind.MAIN_HUB,
        7819393556,
    ),
)

LOCAL_STOPS = (
    StopSeed(
        "Jaszkowa Dolna nż",
        "Jaszkowa Dolna",
        50.4187320,
        16.6664535,
        StopKind.LOCAL,
        9442286043,
    ),
    StopSeed(
        "Jaszkowa Górna Kowale",
        "Jaszkowa Górna",
        50.4023780,
        16.7508534,
        StopKind.LOCAL,
        1818292687,
    ),
    StopSeed("Żelazno", "Żelazno", 50.3714083, 16.6748362, StopKind.LOCAL, 9442082764),
    StopSeed(
        "Krosnowice Kłodzkie",
        "Krosnowice",
        50.3913554,
        16.6502883,
        StopKind.LOCAL,
        10150932731,
    ),
    StopSeed(
        "Krosnowice D.K.",
        "Krosnowice",
        50.3913503,
        16.6363786,
        StopKind.LOCAL,
        9442082762,
    ),
    StopSeed(
        "Krosnowice II nż (PGR)",
        "Krosnowice",
        50.3984310,
        16.6264531,
        StopKind.LOCAL,
        9323799455,
    ),
    StopSeed(
        "Stary Wielisław",
        "Stary Wielisław",
        50.4014538,
        16.5680761,
        StopKind.LOCAL,
        9442596217,
    ),
    StopSeed(
        "Stary Wielisław 29 nż",
        "Stary Wielisław",
        50.4077746,
        16.5962603,
        StopKind.LOCAL,
        9442593514,
    ),
    StopSeed(
        "Szalejów Dolny",
        "Szalejów Dolny",
        50.4261122,
        16.5888667,
        StopKind.LOCAL,
        9453522317,
    ),
    StopSeed(
        "Szalejów Dolny (zamek)",
        "Szalejów Dolny",
        50.4244737,
        16.5951959,
        StopKind.LOCAL,
        9453493316,
    ),
    StopSeed(
        "Szalejów Górny",
        "Szalejów Górny",
        50.4274305,
        16.5498833,
        StopKind.LOCAL,
        9453522320,
    ),
    StopSeed("Wolany", "Wolany", 50.4340714, 16.5270239, StopKind.LOCAL, 9453522322),
    StopSeed(
        "Wolany - Polanica Górna",
        "Wolany",
        50.4383267,
        16.5179136,
        StopKind.LOCAL,
        9453522323,
    ),
    StopSeed("Gorzanów", "Gorzanów", 50.3516004, 16.6354806, StopKind.LOCAL, 9442082766),
    StopSeed(
        "Stary Waliszów",
        "Stary Waliszów",
        50.3219584,
        16.6606270,
        StopKind.LOCAL,
        9399368952,
    ),
    StopSeed(
        "Stary Waliszów kółko rolnicze",
        "Stary Waliszów",
        50.3218379,
        16.6847801,
        StopKind.LOCAL,
        9442082780,
    ),
    StopSeed(
        "Stary Waliszów poczta",
        "Stary Waliszów",
        50.3119439,
        16.6979347,
        StopKind.LOCAL,
        9442082786,
    ),
    StopSeed(
        "Nowa Bystrzyca",
        "Nowa Bystrzyca",
        50.3017911,
        16.5875871,
        StopKind.LOCAL,
        9442082802,
    ),
    StopSeed(
        "Nowa Bystrzyca szkoła",
        "Nowa Bystrzyca",
        50.2944341,
        16.5766225,
        StopKind.LOCAL,
        9442082801,
    ),
    StopSeed(
        "Stara Bystrzyca I",
        "Stara Bystrzyca",
        50.3050357,
        16.6121195,
        StopKind.LOCAL,
        8891110970,
    ),
    StopSeed(
        "Wilkanów PKS",
        "Wilkanów",
        50.2669578,
        16.6609802,
        StopKind.LOCAL,
        5305562848,
    ),
    StopSeed(
        "Wilkanów Szkoła",
        "Wilkanów",
        50.2479630,
        16.6940476,
        StopKind.LOCAL,
        5305562856,
    ),
    StopSeed(
        "Wilkanów Górny",
        "Wilkanów",
        50.2429165,
        16.7110217,
        StopKind.LOCAL,
        5305562862,
    ),
    StopSeed(
        "Długopole-Zdrój",
        "Długopole-Zdrój",
        50.2460481,
        16.6322876,
        StopKind.LOCAL,
        13384259453,
    ),
    StopSeed(
        "Ołdrzychowice Kłodzkie",
        "Ołdrzychowice Kłodzkie",
        50.3584647,
        16.7235490,
        StopKind.LOCAL,
        4612499142,
    ),
    StopSeed(
        "Trzebieszowice",
        "Trzebieszowice",
        50.3466397,
        16.7759138,
        StopKind.LOCAL,
        9333543511,
    ),
    StopSeed(
        "Trzebieszowice transformator",
        "Trzebieszowice",
        50.3488488,
        16.7644151,
        StopKind.LOCAL,
        9442082772,
    ),
    StopSeed("Radochów", "Radochów", 50.3397525, 16.8176518, StopKind.LOCAL, 7489111912),
    StopSeed(
        "Stara Łomnica - Kościół",
        "Stara Łomnica",
        50.3518582,
        16.5808878,
        StopKind.LOCAL,
        13384259457,
    ),
    StopSeed(
        "Wojciechowice Szkoła",
        "Wojciechowice",
        50.4531726,
        16.7066832,
        StopKind.LOCAL,
        9442286038,
    ),
    StopSeed("Korytów", "Korytów", 50.4554762, 16.6038051, StopKind.LOCAL, 9453522326),
    StopSeed("Roszyce", "Roszyce", 50.4481806, 16.5811349, StopKind.LOCAL, 9453522324),
)

STOP_SEEDS = DESTINATION_STOPS + LOCAL_STOPS


def seed_stops(session: Session) -> tuple[int, int]:
    """Insert or update all curated stops and return created/updated counts."""

    created = 0
    updated = 0

    for seed in STOP_SEEDS:
        stop = session.scalar(
            select(Stop).where(
                Stop.source == StopSource.OSM,
                Stop.source_reference == seed.source_reference,
            )
        )

        if stop is None:
            stop = Stop(
                source=StopSource.OSM,
                source_reference=seed.source_reference,
                is_active=True,
            )
            session.add(stop)
            created += 1
        else:
            updated += 1

        stop.name = seed.name
        stop.locality = seed.locality
        stop.latitude = seed.latitude
        stop.longitude = seed.longitude
        stop.kind = seed.kind

    return created, updated


def main() -> None:
    with SessionLocal.begin() as session:
        created, updated = seed_stops(session)

    print(f"Stops ready: {created} created, {updated} updated.")


if __name__ == "__main__":
    main()

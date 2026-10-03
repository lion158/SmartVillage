# Synthetic demand generation

## Scope

The demand generator creates a reproducible set of passengers and planned
inbound trip requests for one service day. It is intended for routing
experiments, not for forecasting real passenger behavior.

The current version generates one trip per passenger from a local pickup stop
to a destination stop in Kłodzko, Bystrzyca Kłodzka, or Polanica-Zdrój. Return
trips and late same-day requests are not generated yet.

## Prerequisites

Create the database and seed the stop catalog from `backend/`:

```sh
uv run alembic upgrade head
uv run python -m app.database.seeds.stops
```

## Generate a scenario

```sh
uv run python -m app.demand.generator \
  --date 2026-10-05 \
  --passengers 1000 \
  --seed 42 \
  --name "Large weekday demand"
```

Options:

| Option | Required | Default | Meaning |
| --- | --- | --- | --- |
| `--date` | yes | none | Simulated service date in `YYYY-MM-DD` format |
| `--passengers` | no | `1000` | Number of passengers and inbound requests |
| `--seed` | no | `42` | Seed used for deterministic random generation |
| `--name` | no | generated | Human-readable scenario name |

Every command creates a new scenario. It never deletes or overwrites an
existing scenario. Reusing the same date, passenger count, and seed produces
the same synthetic demand values in a separate scenario.

## Generated data

One run writes:

- one `simulation_scenarios` row;
- one `passengers` row per generated person;
- one `trip_requests` row per generated person.

The scenario starts as `draft` and changes to `demand_ready` only after the
whole dataset is generated successfully in one database transaction.

Every request contains:

- passenger persona;
- local origin stop;
- destination stop;
- trip purpose;
- desired arrival time;
- submission time from the previous day;
- request source `planned` and initial status `pending`.

## Persona and purpose model

| Persona | Target share | Purpose distribution |
| --- | ---: | --- |
| `student` | 30% | 90% school, 10% other |
| `worker` | 40% | 90% work, 10% shopping |
| `senior` | 20% | 45% shopping, 40% healthcare, 15% leisure |
| `occasional` | 10% | 35% shopping, 35% leisure, 15% healthcare, 15% other |

Reduced mobility is also generated probabilistically. Its probability is 30%
for seniors and between 1% and 3% for the other personas.

## Time model

Desired arrival times use bounded normal distributions:

| Purpose | Typical arrival | Allowed range |
| --- | ---: | ---: |
| School | 07:45 | 07:00–08:30 |
| Work | 08:00 | 06:00–09:30 |
| Shopping | 10:30 | 08:30–14:00 |
| Healthcare | 09:30 | 07:30–13:00 |
| Leisure | 13:00 | 09:00–18:00 |
| Other | 11:00 | 07:00–18:00 |

All application times are generated in `Europe/Warsaw` and normalized to UTC
before persistence. Planned requests are submitted between 08:00 and the 20:00
planning cutoff on the previous day.

## Destination model

For every passenger, the generator calculates the distance from the origin
stop to the center of each destination city:

- 75% select the nearest city;
- 25% select a different city;
- alternative cities are weighted by distance and attractiveness;
- healthcare requests have a strong preference for a stop containing
  `Szpital` when such a stop exists in the selected city.

The explicit non-nearest share represents travel driven by workplace, school,
healthcare, or personal preference rather than distance alone.

## Visualize a scenario

Use the scenario identifier printed by the generator:

```sh
uv run python -m app.demand.report --scenario 1
```

The command writes `backend/data/demand_scenario_1.html`. The HTML file is
ignored by Git because it is generated from local database contents.

The report contains:

- passenger and origin-stop totals;
- persona, purpose, destination-city, and arrival-hour charts;
- the busiest origin stops;
- the measured non-nearest-city share;
- demand-sized origin markers;
- destination markers;
- optional demand heatmap and aggregated flow layers.

Open the report directly in a browser. An internet connection is required to
load OpenStreetMap background tiles.

## Optimizer boundary

Storing and generating 1000 passengers is inexpensive. The optimizer should
not build a travel-time matrix with one node per passenger because 1000
passengers would require roughly one million pairwise route calculations.

Before optimization, requests should be aggregated by:

- origin stop;
- destination stop or city;
- compatible desired-arrival time window;
- total passenger count and mobility requirements.

The routing engine can then optimize a few dozen demand groups and assign the
individual passenger requests back to the resulting vehicle visits.

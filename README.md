# Village City

Village City is a demand-responsive public transport system for rural communities with limited access to cities. Residents submit travel needs in advance, and the system uses that demand to generate more efficient routes, departure times, and vehicle assignments. The goal is to reduce unnecessary waiting, improve access to jobs, schools, healthcare, and services, and make better use of available transport resources.

## Project structure

- `backend/` — Python API, managed with `uv` and built with FastAPI.
- `frontend/` — React and TypeScript web client, built with Vite.
- `docs/database-architecture.md` — database model for stops, synthetic demand, and route plans.
- `docs/synthetic-demand.md` — generator assumptions, commands, and visualization workflow.
- `AGENTS.md` — shared project guidance for contributors and AI coding agents.

The application structure is intentionally small at this stage. Add domain-specific modules and folders as the project needs them.

## Pinned development environment

- Python: 3.12.x, selected by `backend/.python-version` and constrained in `backend/pyproject.toml`.
- uv: 0.10.2 or newer.
- Node.js: 22.23.3, selected by `.nvmrc` and `frontend/package.json`.
- npm: 10.9.9, bundled with Node.js 22.23.3 and checked by `frontend/package.json`.
- Python and JavaScript dependency versions: pinned by `backend/uv.lock` and `frontend/package-lock.json`.

Using the pinned runtime versions and lockfiles keeps the development setup consistent across checkouts. Use the same versions for local development and AI coding agents.

## Install the required tools

### Install `uv`

On macOS and Linux, install `uv` if it is missing:

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

On Windows PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Confirm that `uv` is on `PATH` and install Python 3.12:

```sh
uv --version
uv python install 3.12
```

### Install Node.js and npm

Install Node.js 22.23.3 with a version manager such as `nvm`:

```sh
nvm install 22.23.3
nvm use 22.23.3
node --version
npm --version
```

Expected versions are `v22.23.3` and `10.9.9`. On Windows, use `nvm-windows` with the same version commands. You can also download Node.js from the [official Node.js 22 archive](https://nodejs.org/en/download/archive/v22).

## First-time setup after cloning

Clone the repository and enter the checkout. Then install the pinned dependencies:

```sh
git clone <repository-url>
cd <repository-directory>
uv python install 3.12
cd backend
uv sync --locked
cd ../frontend
npm ci
```

`uv sync --locked` installs the Python dependencies at the versions recorded in `backend/uv.lock` and fails if the lockfile needs an update. `npm ci` installs the JavaScript dependencies at the versions recorded in `frontend/package-lock.json`.

If a command reports the wrong runtime version, activate or install the version listed above first. Do not regenerate lockfiles during initial setup.

## Copy-and-paste setup request for an AI agent

After cloning, give your AI coding agent this instruction:

> Read `AGENTS.md` and the setup instructions in `README.md`. Configure this checkout using the pinned runtimes: Python 3.12 with `uv`, and Node.js 22.23.3 with npm 10.9.9. Install the Python dependencies with `uv sync --locked` from `backend/` and the frontend dependencies with `npm ci` from `frontend/`. Do not change application code, dependency manifests, or lockfiles as part of setup. Check and report the runtime versions and whether setup completed. If a required tool is missing, install or activate the documented version; if that cannot be done, explain the blocker instead of substituting another version.

## Start the application locally

Open two terminals from the repository root.

### Backend

```sh
cd backend
uv run alembic upgrade head
uv run python -m app.database.seeds.stops
uv run python -m app.database.stops_map
uv run python -m app.demand.generator --date 2026-10-05 --passengers 1000 --seed 42
uv run python -m app.demand.report --scenario 1
uv run uvicorn app.main:app --reload
```

The starter API responds at `http://127.0.0.1:8000/`, and its health endpoint is `http://127.0.0.1:8000/health`.

The migration command creates the local SQLite database at
`backend/data/smart_village.db`. Set `DATABASE_URL` to override this location.
The seed command inserts or updates the curated stop catalog without creating duplicates.
The map command writes an interactive visualization to `backend/data/stops_map.html`.
The demand command creates a reproducible single-day scenario with synthetic passengers and
planned trip requests.
The report command creates an interactive demand dashboard and map for the selected scenario.
The stop coordinates and source identifiers are derived from
[OpenStreetMap](https://www.openstreetmap.org/copyright) data © OpenStreetMap contributors.

### Frontend

```sh
cd frontend
npm run dev
```

Vite prints the local development URL in the terminal. Create a production build with:

```sh
npm run build
```

## Dependency files

- `backend/pyproject.toml` declares Python dependencies; `backend/uv.lock` pins their resolved versions.
- `frontend/package.json` declares JavaScript dependencies; `frontend/package-lock.json` pins their resolved versions.

After intentionally changing dependencies, update and commit the relevant lockfile. Do not commit virtual environments, `node_modules`, secrets, or local environment files.

# Project guidance for contributors and AI agents

## Project purpose

Village City helps rural communities access cities through demand-responsive public transport. Residents submit travel needs in advance; the system uses that demand to improve routes, departure times, and vehicle assignments, with the aim of reducing unnecessary waiting and improving access to essential destinations.

## Shared conventions

- Write all source code, code comments, commit-facing documentation, and user-facing application text in English.
- Keep changes focused on the requested work. Avoid adding domain behavior or infrastructure without a clear requirement.
- Inspect the existing code and documentation before changing them, and follow established conventions where they exist.
- Keep secrets and personal travel data out of source control. Use environment variables for local configuration and provide safe examples in `.env.example` files when needed.
- When adding or changing dependencies, update the appropriate manifest and lockfile and document any new setup steps.
- Prefer small, readable modules and explicit interfaces. Keep backend and frontend concerns separate.
- Add or update documentation when a change affects setup, architecture, or developer workflows.

## Technology defaults

- Backend: Python 3.12, managed with `uv`; FastAPI is the initial API framework.
- Frontend: React with TypeScript, managed with npm and built with Vite.
- Keep backend dependencies in `backend/pyproject.toml` and frontend dependencies in `frontend/package.json`.
- Do not introduce a database, authentication provider, deployment platform, or additional framework until the project requirements call for it.

## Environment setup

- Follow the first-time setup in `README.md`. Runtime pins are recorded in `backend/.python-version`, `.nvmrc`, and `frontend/package.json`.
- For a fresh checkout, install Python dependencies with `uv sync --locked` from `backend/` and JavaScript dependencies with `npm ci` from `frontend/`.
- Do not change dependency manifests or lockfiles while setting up an environment. Only update them when the user requests a dependency change or a code change requires one.
- If a required runtime is missing or does not match the repository pin, install or activate the pinned runtime. Do not silently substitute another version.
- When asked to set up the repository, report the selected Python, uv, Node.js, and npm versions and any setup failures.

## Local development commands

Run backend commands from `backend/`:

```sh
uv sync --locked
uv run uvicorn app.main:app --reload
uv run ruff check .
uv run ruff format --check .
```

Run frontend commands from `frontend/`:

```sh
npm ci
npm run dev
npm run typecheck
npm run build
```

Keep these commands and the setup instructions in `README.md` accurate as the project evolves.

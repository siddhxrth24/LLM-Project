# SemesTrack

SemesTrack is an offline-first study planner with a local API and web interface. It organizes courses, syllabus topics, uploaded study materials, coverage analysis, study schedules, and AI-assisted lessons.

## Requirements

- Windows 10 or later
- Python 3.12
- uv
- Node.js 22 and npm 10
- Visual Studio C++ Build Tools with the C++ build workload (required by Chroma on Windows)

## Development setup

Install Python 3.12 if needed and synchronize the locked backend dependencies:

```powershell
uv python install 3.12
uv sync --extra dev
```

Install frontend dependencies and build the web interface:

```powershell
Push-Location frontend
npm ci
npm run build
Pop-Location
```

Start the backend and frontend in separate terminals:

```powershell
uv run uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

```powershell
Push-Location frontend
npm run dev -- --host 127.0.0.1
Pop-Location
```

Open <http://127.0.0.1:5173/>. The Vite development server proxies API requests to the local backend on port 8000.

## Local models

Model-dependent features require locally available model files. To download the configured LLM and embedding model while online, run:

```powershell
uv run python scripts/download_models.py
```

The API can run without model files, but embedding, coverage, and lesson-generation features may be unavailable or degraded. Fine-tuning is an optional development workflow and is not required for normal use.

## Tests

```powershell
uv run pytest backend/tests -q
```

## Database upgrades and backups

SQLite schema initialization is versioned. A complete unversioned database is adopted without replacing its records; missing tables are added, and a missing FTS5 index is rebuilt from stored chunks. If existing columns do not match the application schema, startup stops the migration with an error instead of stamping an incompatible database.

Before upgrading, stop SemesTrack and copy the complete `data` directory to a separate backup location. It contains the SQLite database, uploaded documents, and local vector index. To restore, stop the app and restore that directory as a unit. Keep a separate copy of downloaded models in `models/` if they should be preserved.

This project is intended for local, single-user use. A one-command production launcher and packaged distribution are not yet implemented.
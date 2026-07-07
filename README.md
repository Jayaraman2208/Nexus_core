# NexusCore

A production-grade control-plane application for a **5G Network-in-a-Box (NIB)** —
real-time dashboards, idempotent SIM/slice provisioning, an auditable state machine,
and a vendor-agnostic integration layer, built the way the architecture brief specified.

## Stack

| Layer | Technology |
|---|---|
| Frontend | React 18 + Vite, Tailwind CSS, Recharts, WebSockets, JWT auth |
| Backend API | Django 5 + Django REST Framework, versioned `/api/v1/` |
| Real-time | Django Channels + Redis (WebSocket dashboard streaming) |
| Async tasks | Celery + Redis broker + `django-celery-results` |
| Database | PostgreSQL (SQLite fallback for zero-dependency local dev) |
| State machine | `django-fsm` for SIM / network-slice lifecycle |
| Auth | JWT via `djangorestframework-simplejwt` |
| NIB integration | Vendor-agnostic service layer (`nib_integration/service.py`) — ships with a mock client so the whole app runs without physical hardware |

## Project layout

```
nexuscore/
├── backend/
│   ├── nexuscore/        # settings, urls, asgi/wsgi, celery app
│   ├── core/              # models (SIM, Device, NetworkSlice, AuditLog), admin, audit middleware
│   ├── api/                # DRF serializers, viewsets, routing, standardized error handling
│   ├── nib_integration/    # vendor-agnostic NIB client (mock + real HTTP) + Celery tasks
│   ├── realtime/           # Channels consumer + WebSocket routing
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── api/client.js         # axios instance with JWT refresh interceptor
│   │   ├── hooks/useWebSocket.js # live metrics socket with auto-reconnect
│   │   └── components/           # LoginPage, Dashboard, MetricsChart, SimTable
│   └── package.json
├── docker-compose.yml
├── setup.ps1               # one-shot Windows PowerShell installer
└── README.md
```

## Quick start (Windows / PowerShell)

```powershell
git clone <your-repo-url> nexuscore   # or unzip this project
cd nexuscore
.\setup.ps1
```

The script will:
1. Verify Python 3.11+ and Node 20+ are installed.
2. Create a Python virtualenv in `backend\.venv` and install every backend dependency.
3. Copy `.env.example` → `.env`.
4. Start Postgres + Redis via Docker if Docker Desktop is present (otherwise falls back to SQLite, and you'll need Redis running separately for Celery/WebSockets).
5. Run migrations and optionally create a superuser.
6. Install all frontend npm dependencies.

Then, in three terminals:

```powershell
# 1) API + WebSockets
cd backend; .\.venv\Scripts\Activate.ps1
daphne -b 0.0.0.0 -p 8000 nexuscore.asgi:application

# 2) Celery worker
cd backend; .\.venv\Scripts\Activate.ps1
celery -A nexuscore worker -l info

# 3) Frontend
cd frontend
npm run dev
```

Open **http://localhost:5173**.

### Or, with Docker Desktop installed:
```powershell
docker compose up --build
```

## Manual dependency install (if you don't want to use setup.ps1)

```powershell
# Backend
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt

# Frontend
cd ..\frontend
npm install
```

### Full backend dependency list (`requirements.txt`)
```
Django, djangorestframework, djangorestframework-simplejwt, django-cors-headers,
django-filter, django-fsm, channels, channels-redis, daphne, celery, redis,
django-celery-results, psycopg2-binary, python-dotenv, requests, gunicorn, whitenoise
```

### Full frontend dependency list (`package.json`)
```
react, react-dom, react-router-dom, axios, recharts, lucide-react
(+ dev: vite, @vitejs/plugin-react, tailwindcss, postcss, autoprefixer, eslint)
```

## How the architecture maps to the brief

- **Real-time dashboards** → Channels `NetworkMetricsConsumer` + `useNetworkMetricsSocket` hook, backed by a Celery-beat task (`broadcast_live_metrics`) that polls the NIB and pushes to a channel-layer group.
- **Async task management** → Celery tasks (`provision_sim_task`, `provision_network_slice_task`) so the UI gets an immediate `202 Accepted` while provisioning happens in the background.
- **NIB integration layer** → `nib_integration/service.py` defines `BaseNIBClient`; swap `MockNIBClient` for `HTTPNIBClient` (or a new vendor class) by flipping `NIB_USE_MOCK` in `.env` — nothing else in the codebase changes.
- **Idempotent operations** → `SIM.nib_request_id` is a unique idempotency key; retrying `/api/v1/sims/provision/` with the same `client_request_id` returns the existing SIM instead of creating a duplicate.
- **Transactional integrity** → `transaction.atomic()` wraps every multi-step state change (SIM creation, state transitions).
- **State machines** → `django-fsm` on `SIM.state` and `NetworkSlice.state` (`pending → provisioning → active → suspended/failed`), enforced at the model level so invalid transitions raise immediately.
- **Standardized error handling** → `api/exceptions.py` wraps DRF's handler so every error returns `{"error": {"code", "message", "details"}}`, including a dedicated `NIBIntegrationError` mapped to `502`.
- **Audit trail** → `core.middleware.AuditLogMiddleware` records every mutating API call (who, what, when, status) into `AuditLog`, visible read-only in Django admin.
- **Security** → JWT auth (short-lived access + rotating refresh tokens), CORS locked to the frontend origin, Django's built-in CSRF/XSS/SQL-injection protections.

## Notes & next steps

- The NIB integration ships in **mock mode** (`NIB_USE_MOCK=True`) so you can run and demo the entire app — dashboard, provisioning flow, state machine, audit trail — without physical hardware. Point `NIB_API_BASE_URL` / `NIB_API_KEY` at your real box and set `NIB_USE_MOCK=False` when ready.
- `USE_SQLITE=True` in `.env` lets you skip Postgres entirely for local dev; switch to `False` (and provide `POSTGRES_*` settings) for anything resembling production.
- A static Celery Beat schedule (`CELERY_BEAT_SCHEDULE` in `settings.py`) broadcasts live NIB metrics every 3 seconds. Start it with `celery -A nexuscore beat -l info` (or use the `celery_beat` service in `docker-compose.yml`) alongside the worker.

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

S.A.D.E. (Sistema de Administración de Disponibilidad y Emergencias) — a Flask web app for
tracking driver trips, vehicles, and emergency alerts for a fleet. Spanish is the language of all
identifiers, templates, and user-facing text; keep new code consistent with that.

## Setup & running

Dependencies live in `requirements.txt` (there is also a stray, apparently unused `.venv/`;
prefer `venv/`). Key packages: Flask, Flask-Login, Flask-SQLAlchemy, psycopg2-binary,
python-dotenv, SQLAlchemy, twilio, APScheduler, itsdangerous. If you add a new dependency,
`pip install` it into `venv/` and regenerate `requirements.txt` (`pip freeze`).

```bash
venv/Scripts/activate                # PowerShell: venv/Scripts/Activate.ps1
pip install -r requirements.txt

python run.py                        # creates tables via db.create_all() and starts the dev server on :5000
python seed.py                       # idempotent: seeds one admin, one conductor, one mecanico user
flask --app run.py crear-admin       # interactive CLI command to create an admin account (never an HTTP route)
```

Config is loaded from a `.env` file (see `config.py` for the full list of variables: `SECRET_KEY`,
`DB_USER`/`DB_PASSWORD`/`DB_HOST`/`DB_PORT`/`DB_NAME` or a single `DATABASE_URL`, and
`TWILIO_ACCOUNT_SID`/`TWILIO_AUTH_TOKEN`/`TWILIO_WHATSAPP_FROM`/`TWILIO_SMS_FROM`). The database
is PostgreSQL. There is no migration tool (no Alembic/Flask-Migrate) — schema changes happen by
editing models and re-running `db.create_all()`, which only creates missing tables and will not
alter existing ones.

There are no tests and no linter/formatter configuration in this repo yet.

## Architecture

Classic MVC on top of Flask, structured as one blueprint per role/domain area under
`app/controllers/`, registered in `app/__init__.py`'s `create_app()`:

- `auth` (`/`) — login/logout, and `/` redirects to the correct dashboard based on role.
- `admin` (`/admin`), `conductor` (`/conductor`), `mecanico` (`/mecanico`) — one dashboard per
  role, each gated by a `current_user.es_admin()/es_conductor()/es_mecanico()` check at the top
  of the view rather than a shared decorator.
- `emergencia` (`/emergencia`) — panic-button endpoint (`POST /emergencia/activar`), fully
  implemented: creates the `Emergencia`/`Alerta` rows and sends WhatsApp + SMS via
  `app/services/notificaciones.py`. GPS coordinates are optional (`latitud`/`longitud` are
  nullable) — if the browser couldn't get a location, the alert is still registered and
  notified, just without coordinates.
- `scheduler.py` is not a blueprint by design (it has no HTTP routes) — it's the periodic job
  module for APScheduler. `revisar_viajes_activos()` is fully implemented and scheduled every
  60 seconds from `app/__init__.py`'s `_iniciar_scheduler()`.

**Roles are a single column, not a permissions table.** `Usuario.rol` is a string constrained by
a DB `CheckConstraint` to `'admin' | 'conductor' | 'mecanico'`, mirrored by the `es_admin()` /
`es_conductor()` / `es_mecanico()` helper methods on the model. A `Usuario` optionally links to a
`Conductor` row via `id_conductor` (only meaningful when `rol == 'conductor'`) — the driver's
profile data (license, emergency contact) lives on `Conductor`, not `Usuario`.

**Domain flow**: `Conductor` + `Vehiculo` are paired into a `Viaje` (trip). A vehicle can only
have one `activo` trip at a time — enforced by a partial unique index in the database
(`idx_viaje_activo_unico`), which is **not** expressed in the SQLAlchemy model; any code that
creates a `Viaje` (e.g. driver check-in) must replicate that check at the application level before
inserting. `Viaje.estado` progresses through `activo → completado`, or diverts to `alerta` /
`emergencia` / `cerrado_admin`. `Alerta` (delay/panic/expired-license warnings, with a
1–3 priority) and `Emergencia` (optional GPS coordinates plus per-channel WhatsApp/SMS delivery status)
both hang off a `Viaje`. `ReporteAveria` records vehicle breakdowns and captures the vehicle's
prior `estado`. `Bitacora` is a generic audit log keyed by `(tabla_afectada, registro_id)`.

Every model's check-constrained string columns (`rol`, `estado`, `tipo`, `estado_envio_*`) are the
source of truth for valid states — check the `CheckConstraint` in the model file rather than
assuming which values are legal.

Twilio (WhatsApp + SMS) is wired into the `emergencia` blueprint for emergency notifications.
APScheduler runs `revisar_viajes_activos()` (`app/controllers/scheduler.py`) every 60 seconds to
flag `activo` trips that passed their ETA without confirming arrival. Both default to a
simulated mode (`SIMULATE_TWILIO=True` / no real Twilio calls) unless configured otherwise in
`.env` — see `config.py`.

Templates use Jinja2 with Bootstrap 5 (loaded from CDN in `base.html`) and are organized by
blueprint under `app/templates/<blueprint>/`; `app/static/` currently has no assets.

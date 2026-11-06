# Diet Balancer

A nutrition tracker connected to an ESP32 smart food dispenser. You set up a profile,
get estimated calorie and macro targets, log meals, get rule-based food suggestions,
and dispense food by weight. Food from the dispenser is logged with the weight the
**load cell measured**, never the amount requested.

> Calorie and macro targets are estimates (Mifflin-St Jeor), not medical advice.

## Architecture

```
 React (Vite, Tailwind, Recharts)  ──HTTPS/JSON + JWT──▶  FastAPI  ──SQLAlchemy──▶  PostgreSQL
                                                          ▲
 ESP32 firmware  ──HTTP polling + X-Device-Token──────────┘
 (HX711, 2 servos, SH1106 OLED)
```

* **Backend** (`backend/`): FastAPI with versioned REST under `/api/v1`. Route handlers
  are thin; the logic lives in `app/services/`. Business errors use a single JSON shape:
  `{"error": {"code", "message", "details"}}`.
* **Connecting a dispenser (no code editing):** flash the firmware once. The dispenser
  opens a setup hotspot for Wi-Fi, finds the server by mDNS, and shows a 6-digit code.
  You enter that code under Smart Dispenser → Connect a dispenser, which lists
  dispensers found on your network. See `hardware/esp32/README.md`.
* **Device protocol:** the ESP32 always initiates. It registers, sends a heartbeat every
  10 s, polls `commands/next` every 2 s, then acks, reports progress and posts the result.
  This works behind a home router.
* **Command lifecycle:** `pending → acknowledged → dispensing → completed | failed | cancelled`,
  plus `expired` if the device never picks a command up (60 s). Guarantees:
  * One active command per device, enforced by a partial unique index.
  * Idempotent creation via the `Idempotency-Key` header.
  * Idempotent acks and results, and at most one meal entry per command
    (a `UNIQUE` foreign key on the meal entry).
  * The meal entry is written in the **same transaction** as the completed result.
* **Smart containers:** type only the food name ("rice", "anda", "badam"). The app
  matches it against the built-in catalogue (with Hindi/Telugu aliases) and, when
  `USDA_API_KEY` is set, USDA FoodData Central. You confirm the exact food; nutrition per
  100 g comes from the database (never typed by you and never generated). Categories
  (Protein / Carbohydrates / Fat / Fiber / Mixed, often several) are computed from those
  values by transparent rules (`app/services/nutrition_classifier.py`).
* **Generate My Meal / Serve Meal:** `app/services/meal_planner.py` balances calories,
  protein, carbs and fat together, counting every macronutrient of every food. Overshoot
  is penalised 3×, the day's remaining calories are a hard cap, and each food is limited
  to 3 servings. Portions are editable. Serving queues one measured dispense per food;
  a safety failure (sensor, emergency stop, reboot) cancels the rest, while an empty or
  jammed container only skips that food.
* **Approximate dispensing:** ±10 % tolerance (configurable) with a minimum in grams. Each
  result is reported as on target, over or under, and nutrition is **always** computed from
  the measured weight. Each container learns how much food keeps falling after its gate
  closes ("close early" auto-tuning), so accuracy improves with use.
* **Recommendations:** a deterministic rule engine behind a `RecommendationEngine`
  interface, so an AI engine can be added later without API changes.

## Project structure

```
diet-balancer/
├── backend/            FastAPI app, Alembic migrations, pytest suite, device simulator
│   ├── app/{api/v1/endpoints,core,db,models,schemas,services,repositories,middleware,utils}
│   ├── migrations/     Alembic (0001 initial schema)
│   ├── scripts/simulate_device.py
│   └── tests/
├── frontend/           React app (src/{api,components,context,hooks,layouts,pages,utils,test})
├── hardware/esp32/     PlatformIO firmware, host logic tests, bench test procedure
├── docker-compose.yml
└── .env.example
```

Database tables: `users`, `user_profiles`, `fitness_goals`, `food_items`, `meal_entries`,
`devices`, `device_containers`, `dispensing_commands`, `dispensing_logs`, `device_events`.

There is deliberately no `daily_nutrition_summaries` table. Daily totals come from a
`GROUP BY` over indexed meal entries, which avoids data that can drift out of sync.
Meal entries do store a nutrition *snapshot*, so past days don't change if a food's
reference values are corrected later.

## Quick start with Docker

Prerequisite: Docker Desktop (or Docker Engine + Compose v2). Run in the repository root:
```bash
cp .env.example .env          # then edit POSTGRES_PASSWORD and JWT_SECRET_KEY
docker compose up --build
```
* Web app: http://localhost:8080
* mDNS can't leave Docker's default bridge network, so dispensers can't find a
  Dockerised backend automatically. Type `http://<computer-LAN-IP>:8000/api/v1` on the
  dispenser's setup page (or run the backend outside Docker).
* API docs (Swagger): http://localhost:8000/docs

The backend container runs migrations and seeds the food catalogue on every start (both
are safe to repeat).

## Local development (without Docker)

Prerequisites: Python 3.12+, Node.js 20+, PostgreSQL 14+.

**1. Database** (any terminal):
```bash
psql -U postgres -c "CREATE USER diet WITH PASSWORD 'diet' CREATEDB;"
psql -U postgres -c "CREATE DATABASE diet_balancer OWNER diet;"
psql -U postgres -c "CREATE DATABASE diet_balancer_test OWNER diet;"   # for tests
```

**2. Backend.** Run in `backend/`:
```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                 # set JWT_SECRET_KEY
alembic upgrade head
python -m app.db.seed
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
`--host 0.0.0.0` is what lets the ESP32 on your Wi-Fi reach the API.

**3. Frontend.** Run in `frontend/`:
```bash
npm install
cp .env.example .env                 # VITE_API_BASE_URL=http://localhost:8000/api/v1
npm run dev                          # http://localhost:5173
```

**4. Try the dispenser without hardware (optional).** In `backend/` with the venv active:
```bash
python scripts/simulate_device.py
# prints a 6-digit pairing code, exactly like the OLED would; enter it in the web app
# (Smart Dispenser -> Connect a dispenser). Add --fail no_flow or --fail sensor to test failures.
```
This is a **simulation** of the device protocol; it says nothing about the physical dispenser.

**5. Real ESP32:** see [`hardware/esp32/README.md`](hardware/esp32/README.md).

## Tests

| Suite | Directory | Command | Result at hand-off |
|---|---|---|---|
| Backend (89 tests, real PostgreSQL) | `backend/` | `pytest` | all pass |
| Frontend (26 tests, Vitest + Testing Library) | `frontend/` | `npm test` | all pass |
| Firmware logic (10 simulated scenarios) | `hardware/esp32/` | see its README | all pass |
| Firmware compile | `hardware/esp32/` or `hardware/arduino_ide/` | `pio run` / Arduino IDE | compiled, 0 warnings (ESP32 cores 3.0.7 and 2.0.17) |

Backend tests use `TEST_DATABASE_URL` (default
`postgresql+psycopg://diet:diet@localhost:5432/diet_balancer_test`).

## Verification status

| Item | Status |
|---|---|
| Migrations up/down, `alembic check` (no model drift) | Verified on PostgreSQL 16 |
| API running, health check, CORS preflight | Verified |
| UI rendered against the live API + simulated device | Verified in headless Chromium (desktop) |
| Pairing end-to-end (found nearby → code → online) | Verified through the UI with the simulated device |
| Configure container → Generate My Meal → Serve Meal → measured log | Verified through the UI with the simulated device |
| USDA FoodData Central lookup | Parser and import tested with recorded data; **live API not reachable from the build environment** |
| mDNS advertising of the API | Verified advertised and discovered on one machine; not yet on a real Wi-Fi network |
| Wi-Fi setup hotspot and setup page | Compiles; **not tested on hardware** |
| Docker Compose | **Not run** (Docker was not available in the build environment) |
| Firmware on real ESP32 / servos / HX711 / OLED | **Not tested on hardware.** Follow the bench procedure. |
| HX711 calibration factor | Set from your verified test sketch (-191873.0 kg → -191.873 per gram); confirm with bench step B |
| Servo open/closed angles | **Not known.** You enter them per container after the servo bench test. |
| Dispensing strategy defaults (in-flight 8 g, etc.) | Untested starting points; tune on hardware |

## Feature checklist

Completed:
- [x] Registration, login, logout, "sign out everywhere", password change (Argon2id, JWT with revocation)
- [x] Profile setup wizard, BMR/TDEE/goal targets with a shown calculation, weight update
- [x] Food catalogue: 47 items with sources, all flagged approximate; private custom foods
- [x] Food search, meal logging per meal, edit/delete, daily and weekly views
- [x] Dashboard: calorie ring, macro bars, 4 charts, meals, suggestions, dispenser status
- [x] Rule-based recommendations respecting diet type, allergies and restriction keywords
- [x] Smart containers: food identified from its name, categories, photo, confirmation, history
- [x] Generate My Meal / Serve Meal with editable portions and sequenced, measured dispensing
- [x] ±10 % tolerance reporting (on target / over / under) and per-container auto-tuning
- [x] Weekly and monthly reports
- [x] Device registration, token auth (hashed, shown once, rotatable), heartbeat, events
- [x] Configurable container ↔ servo ↔ food mapping, configurable dispensing strategy
- [x] Dispense, tare, cancel, emergency stop (web, device, serial), log-measured-after-failure
- [x] ESP32 firmware: dual-core design, Wi-Fi/backend reconnection, OLED, serial bench console
- [x] Rate limiting on auth endpoints, centralised errors, request IDs, CORS

Pending / suggested next:
- [ ] Hardware bench tests (owner, on the real device)
- [ ] Docker Compose run on a machine with Docker
- [ ] HTTPS for remote access (put the API behind a TLS reverse proxy and add `API_ROOT_CA` to the firmware)
- [ ] External nutrition API (the `FoodItem.source` field and custom foods are ready for it)
- [ ] Account deletion and data export
- [ ] Multi-load-cell support (the schema allows more containers and servos; per-container weighing needs firmware work)

## Security notes

* Passwords are hashed with Argon2id. JWTs expire after 12 h and carry a `token_version`,
  so password changes and "sign out everywhere" revoke old tokens.
* Device tokens are random (256-bit) and stored as SHA-256 hashes. They're created at
  pairing and delivered only to the dispenser holding its own random pairing secret;
  the server's copy is wiped once used. Claiming needs the 6-digit code shown on the
  dispenser's screen, and claims are rate-limited. Tokens never appear in frontend code.
  On a home LAN the device talks plain HTTP; for remote servers use HTTPS
  (`API_ROOT_CA` in `config.h`).
* Users only ever see their own data; other users' resources return 404.
* Server secrets live in `.env` files (git-ignored). The firmware contains no secrets; a dispenser keeps its Wi-Fi password and token in its own flash.
* The rate limiter is in-memory (single process). Use proxy-level limits if you scale out.
* The web token is kept in `localStorage`. That's a common SPA trade-off; keep the
  frontend free of third-party scripts.

## Troubleshooting

* **The OLED says "Server not found":** the backend must listen on `0.0.0.0`, the
  firewall must allow port 8000, and mDNS must reach your network. Otherwise type
  `http://<computer-LAN-IP>:8000/api/v1` on the dispenser's setup page.
* **The dispenser isn't in "Found nearby":** your phone or computer must be on the same
  Wi-Fi. You can always use **I have a code** instead.
* **"Dispenser is offline":** no heartbeat in 30 s. Check the serial monitor.
* **"Scale isn't calibrated":** run `cal <grams>` over serial (see the hardware README).
* **CORS error in the browser:** add the web app's origin to `CORS_ORIGINS`.

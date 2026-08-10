# Smart Campus — FastAPI Backend

A complete, production-ready backend for the **Smart Campus** academic management
& learning system. It implements the exact API contract the frontend expects, so
you can point the existing React app at this server **without changing a single
line of frontend code** — just flip two environment variables.

- **FastAPI** + **SQLAlchemy 2.0** + **Pydantic v2**
- **SQLite** out of the box (zero config), swap to **PostgreSQL** with one env var
- **JWT** auth (access + refresh), password hashing via stdlib **PBKDF2-HMAC-SHA256**
- Rotating-QR **TOTP** attendance, **geofencing**, **device binding**, **CBT exams**
- Auto-seeds a full demo dataset (departments, programs, courses, users, exams…)
- Pure-Python dependencies — installs cleanly on Windows/macOS/Linux with no compiler

---

## 1. Quick start

You need **Python 3.10+** (tested on 3.12).

```bash
# 1. (recommended) create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. install dependencies
pip install -r requirements.txt

# 3. run the server
uvicorn app.main:app --reload --port 8000
```

That's it. On first start the database (`smart_campus.db`) is created and seeded
automatically. The API is now live at:

- API base: **http://localhost:8000/api**
- Interactive docs (Swagger): **http://localhost:8000/docs**
- Health check: **http://localhost:8000/health**

> On Windows you can also just double-check things with `python -m uvicorn app.main:app --port 8000`.

---

## 2. Demo accounts

Every seeded account uses the password **`password`**.

| Role     | Email                    | Name              | Notes                          |
|----------|--------------------------|-------------------|--------------------------------|
| Admin    | `admin@campus.edu.gh`    | Ama Boateng       | Full system administration     |
| Lecturer | `lecturer@campus.edu.gh` | Dr. Michael Opoku | HOD, Computer Science          |
| Student  | `student@campus.edu.gh`  | Joseph Abugah     | BSc Computer Science, Level 300 |

The richest demo data lives in the **BSc Computer Science · Level 300 · Semester 1**
cohort (courses CSC 301 / 305 / 307 / 309): a live attendance session, materials,
assignments with submissions, an open quiz, notifications and audit logs.

---

## 3. Connecting the frontend

The frontend already talks to this exact contract through its API client. To make
it use this backend instead of its built-in mock, set these in the **frontend's**
`.env` (e.g. `.env.local`) and restart its dev server:

```env
VITE_USE_MOCK=false
VITE_API_BASE_URL=http://localhost:8000/api
```

That's the whole integration — auth, role scoping, error messages and status codes
all match the mock, so the app behaves identically against the real server.

### Optional: Vite dev proxy (avoids CORS entirely)

If you'd rather serve the API under the same origin during development, add a proxy
to the frontend's `vite.config.ts` and set `VITE_API_BASE_URL=/api`:

```ts
export default defineConfig({
  // ...
  server: {
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});
```

CORS is already open by default (`CORS_ORIGINS=*`), so the direct approach works
without a proxy too.

---

## 4. Configuration

All settings have safe defaults; the server runs with **no `.env` file**. To
override, copy `.env.example` to `.env` and edit. Key variables:

| Variable                       | Default                          | Purpose                                   |
|--------------------------------|----------------------------------|-------------------------------------------|
| `DATABASE_URL`                 | `sqlite:///./smart_campus.db`    | Any SQLAlchemy URL (see PostgreSQL below) |
| `SECRET_KEY`                   | dev placeholder                  | **Change in production** — JWT signing key |
| `ACCESS_TOKEN_EXPIRE_MINUTES`  | `720` (12h)                      | Access-token lifetime                     |
| `REFRESH_TOKEN_EXPIRE_MINUTES` | `20160` (14d)                    | Refresh-token lifetime                    |
| `CORS_ORIGINS`                 | `*`                              | Comma-separated allowed origins           |
| `SEED_ON_STARTUP`              | `true`                           | Seed demo data when the DB is empty       |

---

## 5. Using PostgreSQL (production)

```bash
pip install "psycopg[binary]"
export DATABASE_URL="postgresql+psycopg://user:password@localhost:5432/smart_campus"
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Tables are created automatically on startup. The demo seed still runs once if the
database is empty — set `SEED_ON_STARTUP=false` to disable it for a clean install.

---

## 6. Project structure

```
smart-campus-backend/
├── app/
│   ├── main.py            # FastAPI app, CORS, router mounting, startup seeding
│   ├── config.py          # Settings (env-driven, sane defaults)
│   ├── database.py        # Engine, session factory, get_db dependency
│   ├── models.py          # SQLAlchemy ORM models (mirror frontend types)
│   ├── schemas.py         # Pydantic request models
│   ├── security.py        # JWT, password hashing, TOTP, geofence math
│   ├── deps.py            # Auth dependencies & role guards
│   ├── enrich.py          # Response serialisers (exact JSON shapes) + helpers
│   ├── seed.py            # Demo dataset (matches the frontend mock exactly)
│   └── routers/
│       ├── auth.py            # /auth/* + refresh
│       ├── institution.py     # /departments, /programs, /academic/period
│       ├── courses.py         # /courses*
│       ├── attendance.py      # /attendance/*  (TOTP + geofence + device binding)
│       ├── materials.py       # /materials*
│       ├── assignments.py     # /assignments*, /submissions/*
│       ├── exams.py           # /exams*, /attempts/*
│       ├── analytics.py       # /analytics/*
│       ├── notifications.py   # /notifications*
│       └── admin.py           # /admin/*
├── requirements.txt
├── .env.example
└── README.md
```

---

## 7. API reference

All endpoints are under the `/api` prefix and (except login/register/forgot-password)
require an `Authorization: Bearer <access_token>` header.

**Auth** — `POST /auth/login`, `POST /auth/register`, `POST /auth/forgot-password`,
`GET /auth/me`, `POST /auth/refresh`

**Institution** — `GET /departments`, `GET /departments/{id}`, `POST /departments`,
`PATCH /departments/{id}`, `GET /programs`, `POST /programs`,
`GET /academic/period`, `PATCH /admin/academic-period`

**Courses** — `GET /courses` (role-scoped, filters: `department_id`, `program_id`,
`level`, `semester`, `year`, `current`), `GET /courses/{id}`, `POST /courses`,
`GET /courses/{id}/students`

**Attendance** — `GET /attendance/sessions`, `POST /attendance/sessions`,
`POST /attendance/sessions/{id}/close`, `GET /attendance/sessions/{id}/records`,
`POST /attendance/sessions/{id}/mark`, `GET /attendance/my`

**Materials** — `GET /materials` (`?course_id=`), `POST /materials`,
`DELETE /materials/{id}`, `POST /materials/{id}/access`

**Assignments** — `GET /assignments` (`?course_id=`), `POST /assignments`,
`GET /assignments/{id}/submissions`, `POST /assignments/{id}/submit`,
`POST /submissions/{id}/grade`

**Exams (CBT)** — `GET /exams`, `GET /exams/{id}`, `POST /exams`,
`POST /exams/{id}/attempts/start`, `GET /exams/{id}/attempts/me`,
`PATCH /attempts/{id}`, `POST /attempts/{id}/submit`, `GET /exams/{id}/attempts`

**Analytics** — `GET /analytics/dashboard`, `GET /analytics/course/{id}`,
`GET /analytics/overview`

**Notifications** — `GET /notifications`, `POST /notifications/{id}/read`,
`POST /notifications/read-all`

**Admin** — `GET /admin/users`, `POST /admin/users`, `PATCH /admin/users/{id}`,
`GET /admin/audit`, `GET /admin/settings`, `PATCH /admin/settings`,
`POST /admin/reset-demo`

Full request/response schemas are browsable at `/docs`.

---

## 8. How the security features work

- **Rotating-QR attendance (TOTP).** Each session carries a `totp_seed` and
  `rotate_seconds`. A new 6-digit token is derived every rotation window using the
  same deterministic algorithm the frontend uses, so a screenshotted QR expires
  almost immediately. The server accepts the current window's token and the
  previous one (a small grace window for clock drift).
- **Geofencing.** Marking is rejected (HTTP 422) if the device is farther than the
  session's radius from the session coordinates (haversine distance).
- **Device binding.** A student who has marked present from one device cannot mark
  from a different one without an admin reassignment.

> Note: the attendance TOTP here is the lightweight, deterministic scheme the
> frontend demo is designed around (so the client can render the live QR). It is
> **not** RFC 6238. To harden for production, move token generation fully
> server-side, return only the current QR image (never the seed), and switch to a
> keyed HMAC (RFC 6238) — the rest of the flow stays the same.

---

## 9. Production checklist

- [ ] Set a strong `SECRET_KEY` (e.g. `python -c "import secrets; print(secrets.token_urlsafe(48))"`)
- [ ] Restrict `CORS_ORIGINS` to your real frontend origin(s)
- [ ] Use PostgreSQL via `DATABASE_URL`
- [ ] Set `SEED_ON_STARTUP=false` for a clean (non-demo) database
- [ ] Run behind a process manager / reverse proxy
      (e.g. `uvicorn` workers behind nginx, or `gunicorn -k uvicorn.workers.UvicornWorker`)
- [ ] Serve over HTTPS

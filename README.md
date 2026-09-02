# RecoverAI

RecoverAI is an AI-powered revenue recovery and payment reconciliation project
for the Razorpay AI Buildathon. This repository currently contains only the
foundation stage: a dashboard shell, versioned FastAPI health API, and
PostgreSQL/Alembic configuration.

## Current architecture

`Frontend (Next.js) → FastAPI → PostgreSQL`

The frontend calls the FastAPI health endpoint to display the backend
connection status. No payment, AI, recovery, or reconciliation features are
implemented yet.

## Current status

Foundation stage complete. The backend is modular and versioned, database
configuration is ready for PostgreSQL, and Alembic is initialized without any
domain tables or migrations.

## Local setup

### 1. Configure environment variables

Copy `.env.example` to `.env` and add only your local configuration. Do not
commit this file. The supplied default `DATABASE_URL` targets the local Docker
PostgreSQL service.

For the frontend, copy `frontend/.env.local.example` to `frontend/.env.local`
if the backend runs anywhere other than `http://localhost:8000`.

### 2. Start PostgreSQL and the backend

```powershell
docker compose up --build
```

This starts PostgreSQL on port 5432 and the backend on port 8000. To start only
PostgreSQL with Docker, run `docker compose up -d postgres`.

### 3. Run the backend locally (alternative)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

The health check is available at `http://localhost:8000/api/v1/health`.

### 4. Run the frontend

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`. When the backend is running, the dashboard shows
**Backend Connected**.

### 5. Run backend tests

```powershell
cd backend
pytest
```

## Environment variables

| Variable | Purpose |
| --- | --- |
| `RAZORPAY_KEY_ID` | Reserved for a later Razorpay integration. |
| `RAZORPAY_KEY_SECRET` | Reserved for a later Razorpay integration. |
| `RAZORPAY_WEBHOOK_SECRET` | Reserved for a later webhook integration. |
| `DATABASE_URL` | SQLAlchemy PostgreSQL connection URL. |
| `AI_API_KEY` | Reserved for a later AI integration. |
| `NEXT_PUBLIC_BACKEND_URL` | Frontend backend URL; defaults to `http://localhost:8000`. |

## Database migrations

Alembic is configured but no tables exist in this stage. Once a database is
running, future migrations can be run from `backend/` with:

```powershell
alembic upgrade head
```

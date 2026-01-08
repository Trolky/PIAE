# PIAE – Translation Service (FastAPI + MongoDB + Django)

A simple translation-project management service.

- **Backend**: FastAPI + MongoDB (Motor), file storage via **GridFS**.
- **Frontend**: Django (server-rendered UI) which calls the backend via HTTP.
- **Emails**: sent to a mocked SMTP server (**MailHog**).

## Architecture

- **Backend** (`/Backend`)
  - API layer: `app/api/*` (FastAPI routers)
  - Service layer: `app/services/*` (business logic)
  - Data layer: `app/repositories/*` (MongoDB queries)
  - Storage: MongoDB collections + GridFS for file blobs
  - Auth: JWT + optional OTP (TOTP)

- **Frontend** (`/Frontend`)
  - Django views in `web/views.py`
  - Backend calls are implemented using a small stdlib client `web/backend_client.py`
  - JWT is stored in Django session (SQLite)
  - File downloads are proxied through Django

## Run (one command, Docker Compose)

From the repository root:

```cmd
docker compose up -d --build
```

### Exposed services

- **Frontend UI**: http://localhost:8001
- **Backend API**: http://localhost:8000
- **MailHog UI**: http://localhost:8025
- **MongoDB**: mongodb://localhost:27017

## How to try the main flows

1. Open the frontend: http://localhost:8001
2. Register a **Customer** and a **Translator**.
3. Log in as Translator and configure target languages in **Languages**.
4. Log in as Customer and create a project (upload any file + choose target language).
5. Translator opens the assigned project, downloads the original file and uploads the translated file.
6. Customer approves/rejects and submits feedback.
7. Administrator can review feedback projects, send messages and close projects.

## Authentication

### JWT (access token)

- Issued by the backend on successful login.
- Frontend stores it in Django session and sends it as:

```
Authorization: Bearer <token>
```

### Second login method: OTP (TOTP)

- User must first log in using username/password.
- Then user can enable OTP in the UI (OTP setup page) and scan the QR / provisioning URI.
- After activation, user can log in using OTP as an alternative method.

## Configuration

Configuration is driven by environment variables (best used via Docker Compose).

### Backend (FastAPI)

Defined in root `docker-compose.yml`:

- `MONGODB_URI` (default in compose: `mongodb://mongo:27017`)
- `MONGODB_DB` (default: `piae`)
- `MAX_UPLOAD_MB` (default: `5`)
- `JWT_SECRET` (dev value in compose)
- `CORS_ALLOW_ORIGINS` (default: `http://localhost:8001`)
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM` (MailHog)
- `OTP_MASTER_SECRET` (dev value in compose)

### Frontend (Django)

- `BACKEND_API_BASE_URL` (default: `http://localhost:8000`)

## Notes on storage

- Project files are stored in **GridFS** (bucket `files`).
- Projects store file references (GridFS file ids).

## Development (optional)

If you want to run components outside Docker:

- Backend deps: `Backend/requirements.txt`
- Frontend deps: `Frontend/requirements.txt`

You still need:
- MongoDB
- MailHog (or any SMTP mock)

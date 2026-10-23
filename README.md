# Job Management API — FastAPI Integration Portfolio

A hands-on integration project demonstrating a job-management REST API, a browser-based CRUD interface, access control, and API troubleshooting workflows.

**Repository:** [indeed-job-api](https://github.com/waxwaxwax/indeed-job-api)

> **Status:** Local development demo. The API is not currently hosted as a public service. Authentication and OAuth functionality are educational implementations, not production identity solutions.

## Project overview

This project simulates a small job-posting integration. A plain HTML/JavaScript client communicates with a Python FastAPI service, which stores job records in SQLite.

```text
Browser (HTML + JavaScript)
          |
          | HTTP / JSON (REST)
          v
    FastAPI application
          |
          v
      SQLite database

Additional capabilities: bearer-token checks, simulated OAuth client-credentials flow,
CORS configuration, request IDs, and rotating application logs.
```

## Key capabilities

- **REST API:** List, create, retrieve, update, and delete job records.
- **Interactive frontend:** Exercise API operations from a browser using `test_frontend_secure.html`.
- **Authorization:** Distinguish unauthenticated requests (`401`) from authenticated requests without sufficient permissions (`403`). Write operations require an administrative bearer token.
- **OAuth learning exercise:** Issue temporary, scoped tokens using a simulated client-credentials flow (`jobs.read` and `jobs.write`). This is not an external OAuth provider.
- **Troubleshooting:** Inspect HTTP status codes, request identifiers, and application logs.
- **Configuration:** Keep secrets and allowed CORS origins in local environment configuration rather than committing credentials.

## API endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/jobs` | List jobs |
| `GET` | `/jobs/{job_id}` | Retrieve a job |
| `POST` | `/jobs` | Create a job (admin token required) |
| `PUT` | `/jobs/{job_id}` | Update a job (admin token required) |
| `DELETE` | `/jobs/{job_id}` | Delete a job (admin token required) |
| `GET` | `/secure/jobs` | Test bearer-token access control |
| `POST` | `/token` | Issue a simulated OAuth access token |
| `GET` | `/oauth/jobs` | Read jobs with a scoped token |
| `POST` | `/oauth/jobs` | Create a job with a scoped token |
| `GET` | `/docs` | Interactive OpenAPI / Swagger UI |

## Authentication and error-handling test cases

The following scenarios were exercised locally:

| Scenario | Expected HTTP response |
| --- | --- |
| Create a job without a bearer token | `401 Unauthorized` |
| Create a job with a read-only token | `403 Forbidden` |
| Create a job with an admin token | `201 Created` |
| Retrieve the job list | `200 OK` |
| Update and delete a job with an admin token | `200 OK` |

The browser interface was also tested against the local FastAPI service for create, read, update, and delete operations.

## Run locally

### Prerequisites

- Python 3.10 or later
- Git
- A modern web browser

### 1. Clone and set up

```bash
git clone https://github.com/waxwaxwax/indeed-job-api.git
cd indeed-job-api
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### 2. Configure environment variables

Create a local `.env` file with the configuration keys required by `main.py`. If an `.env.example` file is available, copy it as a starting point. Generate distinct random values for all secrets and never commit `.env`.

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Consult `SETUP.txt` and `main.py` for the supported configuration names and defaults. For the browser demo, ensure the allowed origins include `http://127.0.0.1:5500`.

### 3. Start the API

```bash
python -m uvicorn main:app --reload
```

Open **http://127.0.0.1:8000/docs** to inspect and exercise the API.

### 4. Start the browser interface

In a second terminal, from the repository directory:

```bash
python3 -m http.server 5500 --bind 127.0.0.1
```

Open **http://127.0.0.1:5500/test_frontend_secure.html**.

The browser interface is for **local testing only**. Do not enter production secrets into a publicly hosted static page.

## Troubleshooting examples

- **`401 Unauthorized`:** Check whether a bearer token was supplied and is valid.
- **`403 Forbidden`:** Check whether the token has the required permission.
- **Browser `Failed to fetch`:** Confirm that both servers are running and that the frontend origin is allowed by CORS.
- **`Address already in use`:** Check whether another process is already listening on port 8000.
- **Unexpected API behavior:** Compare the HTTP response, request ID, and local application log entries.

## Security and production limitations

This is a learning portfolio, **not a production-ready recruitment system**.

- The OAuth client-credentials flow is simulated locally; it does not replace a standards-compliant identity provider.
- The local HTML page accepts a bearer token for testing; it must not be published as a production administrative interface.
- SQLite is appropriate for the local demonstration, but production deployment requires a deliberate persistence, backup, and migration strategy.
- Public hosting would require additional hardening, including secure identity management, least-privilege access, secret management, transport security, and operational monitoring.
- Local `.env` files, SQLite data, virtual environments, logs, and backups are excluded from version control.

## Planned improvements

- Deploy a secured API and durable database to Azure.
- Replace educational authentication with a production-grade identity solution.
- Add automated tests and CI checks.
- Add a GraphQL integration example and deployment documentation.

## What this project demonstrates

The project focuses on the practical work of an integration-focused technical analyst: interpreting API contracts, testing authentication and authorization, tracing request failures, diagnosing CORS and local environment issues, and validating end-to-end data operations.

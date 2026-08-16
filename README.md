# Crack Interviews (Hackerleap)

[![Django tests](https://github.com/v-adhithyan/crack-interviews/actions/workflows/django-ci.yml/badge.svg)](https://github.com/v-adhithyan/crack-interviews/actions/workflows/django-ci.yml)
[![Deploy backend to PythonAnywhere](https://github.com/v-adhithyan/crack-interviews/actions/workflows/deploy-backend-pythonanywhere.yml/badge.svg)](https://github.com/v-adhithyan/crack-interviews/actions/workflows/deploy-backend-pythonanywhere.yml)
[![Vercel deployment](https://img.shields.io/github/deployments/v-adhithyan/crack-interviews/Production?label=vercel&logo=vercel)](https://github.com/v-adhithyan/crack-interviews/deployments/Production)

A personal HackerRank/LeetCode-style practice platform built with Django and Next.js.

See [the architecture overview](docs/architecture.md) for system, AI, request-flow,
and deployment diagrams.

## Stack

- Backend: Django, Django REST Framework, SQLite
- Frontend: Next.js, TypeScript, Tailwind CSS, Monaco Editor
- Runtime: Java 17 submissions by default, with Python 3 still available

## Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Admin: http://localhost:8000/admin/

API health: http://localhost:8000/api/health/

## Frontend

```bash
cd frontend
npm install
npm run dev
```

App: http://localhost:3000

## Running Locally

From a fresh checkout, start the backend first:

```bash
cd /Users/adhithyan.vijayakumar/repos/crack-interviews/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py seed_sample
python manage.py createsuperuser
python manage.py runserver
```

Then start the frontend in a second terminal:

```bash
cd /Users/adhithyan.vijayakumar/repos/crack-interviews/frontend
npm install
cp .env.example .env.local
npm run dev
```

Open:

- Frontend: http://localhost:3000
- Django admin: http://localhost:8000/admin/
- API health check: http://localhost:8000/api/health/

Use Django admin to create questions, add test cases manually, import test cases from CSV, and mark questions active or inactive.

## Run with Docker

### Prerequisites

Install Docker Desktop, or Docker Engine with the Compose plugin. Verify the
installation with `docker --version` and `docker compose version`.

### Quick start

From the repository root, start MySQL, the Django API, the Django-Q worker, and the
Next.js frontend:

```bash
docker compose up --build
```

To run in the background instead, use:

```bash
docker compose up --build --detach
docker compose logs --follow
```

Open the frontend at http://localhost:3000 and Django admin at
http://localhost:8000/admin/. The API health check is available at
http://localhost:8000/api/health/. Database migrations and static-file collection
run automatically when the backend starts. Some endpoints require login. So create a superuser using the below command for login purpose.
Set your chatgpt api key in compose.yaml to directly interact with
chatgpt.

### Initial setup

Create an administrator:

```bash
docker compose exec backend python manage.py createsuperuser
```

Optionally load the sample coding questions:

```bash
docker compose exec backend python manage.py seed_sample
```

### Environment configuration

The checked-in defaults are intended for local development and do not require an
OpenAI API key. To override them:

```bash
cp .env.example .env
```

Edit `.env`, then rebuild with `docker compose up --build`. Keep
`HACKERLEAP_AI_MODE=manual` when AI-backed features are not needed. Never commit an
API key; store `OPENAI_API_KEY` only in the ignored `.env` file or your deployment
platform's secret manager.

### Common commands

```bash
# Show service status
docker compose ps

# Follow one service's logs
docker compose logs --follow backend

# Run the Django test suite
docker compose exec backend python manage.py test

# Stop and remove containers while preserving data
docker compose down

# Delete containers, the MySQL database, and uploaded media
docker compose down --volumes
```

MySQL data and uploaded media are stored in named Docker volumes and survive a
normal `docker compose down`.

### Public deployment

For a public deployment, change every URL/host setting in `.env` to the real HTTPS
domains. `NEXT_PUBLIC_API_BASE_URL` is embedded during the frontend image build, so
rebuild the frontend after changing it. Replace the development Django and MySQL
secrets before deploying.

The backend executes submitted Java and Python programs as local subprocesses.
Running the backend itself in Docker does not safely isolate each submission. Do
not expose code execution to untrusted users without disposable sandboxes, disabled
network access, filesystem isolation, and strict CPU, memory, process, and time
limits.

## Test Case CSV Format

Upload test cases from a question's Django admin detail page using this header:

```csv
name,stdin,expected_output,is_sample,is_hidden,order
Sample 1,"1 2","3",true,false,1
Hidden 1,"5 9","14",false,true,2
```

## Java Runtime

The practice runner targets Java 17. That is the pragmatic baseline for Java interview prep: it is a long-term support release, commonly accepted by coding platforms, and avoids relying on newer language features that may not exist in an interview environment.

Java submissions are compiled with `javac --release 17` and then run once per test case. Code should include a class with a `main` method. `public class Main` is the recommended shape, though the runner will also detect another public class name such as `Solution`.

You can override local executables and limits in the backend environment:

```bash
JAVA_EXECUTABLE=java
JAVAC_EXECUTABLE=javac
JAVA_RELEASE=17
COMPILE_TIMEOUT_SECONDS=8
CODE_TIMEOUT_SECONDS=2
```

## Security Note

The MVP executes submitted code using local subprocesses with timeouts. This is suitable for personal local development only. Do not expose it publicly without container isolation, filesystem/network restrictions, and stronger resource limits.

## License

This project is licensed under the [MIT License](LICENSE).


## Always on task in pythonanywhere

```/home/hackerleap/.virtualenvs/hackerleap.pythonanywhere.com/bin/python /home/hackerleap/hackerleap.pythonanywhere.com/backend/manage.py qcluster```

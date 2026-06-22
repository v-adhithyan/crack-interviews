# Crack Interviews

A personal HackerRank/LeetCode-style practice platform built with Django and Next.js.

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

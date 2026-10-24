# Mock interview simulator

The Django sidebar separates System Design Interview / System Design History from
Mock Interview Simulator / Simulator History. The simulator reuses the voice room,
transcript storage, timer and feedback rendering, but has its own setup, routes,
private history and role/round-specific interviewer and evaluator instructions.

## Setup and repeat practice

Enter company, round (including Other), recruiter briefing, role and job description.
Choose an owned builder draft or parsed uploaded resume. Enable optional experience
matching and company values/vision/mission criteria. Enabled company criteria require
pasted supporting text; there is no automatic company lookup.

Creating a room freezes the setup, resume text/snapshot and generated prompt. The
resume is not modified. History's **Start another interview** opens a reviewable form
with the original setup and saved resume selected, even if the resume was deleted.
Submitting unchanged uses the exact original prompt; edits or a different resume
create a new prompt. The new session starts without old turns, feedback or timer.
The saved prompt is visible under each history entry.

`InterviewSimulatorSession` has its own table for context and inherits the existing
`MockInterviewSession` lifecycle. System-design querysets explicitly exclude simulator
rows; simulator endpoints require ownership, including for staff. Session UUIDs cannot
be used across the two sets of routes. State changes require POST and CSRF protection.
Company data, resumes and transcripts are untrusted context, never trusted instructions.
Disabled company text is omitted from provider requests. AI guidance is not a hiring decision.

## Routes

- GET/POST `/app/interview-simulator/`: setup and room creation
- GET `/app/interview-simulator/history/`: paginated private history
- GET/POST `/app/interview-simulator/<uuid>/reuse/`: review and create a fresh session
- GET `/app/interview-simulator/<uuid>/`: voice room
- POST `.../token/`: ephemeral voice credentials
- POST `.../turns/`: transcript turn
- POST `.../finish/`: generate feedback
- GET `.../feedback/`: feedback and transcript

The existing 60-minute limit and account voice quota apply. Both features share that
quota; setup and prompt reuse alone do not consume it. Token creation serializes
session/allowance updates with database row locks. Failed starts can be retried without
bypassing quota, and reconnecting a started session does not charge another session.
Voice and feedback use the existing OpenAI configuration. No new API keys are needed.

## Deploy

```sh
python backend/manage.py migrate
python backend/manage.py collectstatic --noinput
```

Reload the Django web application. Migration `0026_interviewsimulatorsession` is required.
No new background job or worker configuration is involved.

Tests: `python backend/manage.py test apps.product.test_interview_simulator apps.product.tests`.
They mock AI calls and cover snapshots, reuse, edited setup, validation, privacy,
CSRF, cross-feature isolation, prompt selection, reconnects, quota and feedback routing.
A real microphone/provider acceptance check is still required after deployment.

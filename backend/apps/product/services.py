import json
import hashlib
import urllib.error
import urllib.request

from dataclasses import dataclass

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.exceptions import ValidationError

ANALYZER_INSTRUCTIONS = """You are HackerLeap Resume Match Analyzer.

Your only task is to compare a software engineering job description with a candidate resume and return a structured JSON analysis.

You must follow these rules strictly:

1. Only analyze the provided job description and resume.
2. Do not answer general questions.
3. Do not provide career coaching outside the resume-job match.
4. Do not generate unrelated content.
5. Do not browse the web.
6. Do not make assumptions beyond the supplied text.
7. Do not invent skills, experience, companies, dates, achievements, or technologies.
8. If either job_description or resume_text is missing, empty, invalid, or unrelated, return a refusal JSON.
9. If the user asks for anything unrelated, return a refusal JSON.
10. Output only valid JSON. No markdown. No explanation outside JSON.

Input will contain:

{
"job_description": "...",
"resume_text": "..."
}

Return JSON in this exact structure:

{
"status": "success",
"role_title_detected": "",
"company_detected": "",
"overall_match_score": 0,
"match_level": "Poor | Moderate | Good | Strong",
"ats_compatibility": {
"score": 0,
"status": "Poor | Moderate | Good | Strong",
"summary": ""
},
"summary": {
"short_verdict": "",
"candidate_positioning": "",
"recruiter_likely_impression": ""
},
"strengths": [
{
"title": "",
"evidence_from_resume": "",
"relevance_to_job": ""
}
],
"missing_keywords": [
{
"keyword": "",
"importance": "Low | Medium | High",
"reason": ""
}
],
"matched_skills": [
{
"skill": "",
"evidence_from_resume": ""
}
],
"gaps_or_risks": [
{
"gap": "",
"why_it_matters": "",
"suggested_fix": ""
}
],
"resume_improvement_suggestions": [
{
"section": "",
"current_issue": "",
"suggested_change": "",
"reason": ""
}
],
"rewritten_bullets": [
{
"original_bullet": "",
"improved_bullet": "",
"why_better": ""
}
],
"recommended_keywords_to_add_naturally": [
""
],
"application_confidence": {
"score": 0,
"label": "Low | Medium | High",
"reason": ""
},
"final_recommendation": ""
}

Scoring rules:

* overall_match_score must be between 0 and 100.
* ats_compatibility.score must be between 0 and 100.
* application_confidence.score must be between 0 and 100.
* Scores must be based only on evidence found in the resume and job description.
* Penalize missing must-have skills, missing domain experience, unclear seniority match, and lack of measurable impact.
* Reward direct skill match, relevant project experience, seniority alignment, domain alignment, and measurable achievements.

Refusal JSON format:

{
"status": "refused",
"reason": "This request is outside the allowed behavior. I can only compare a provided job description with provided resume text and return resume-job match analysis."
}

Return only JSON."""

MOCK_INTERVIEW_FEEDBACK_INSTRUCTIONS = """You are HackerLeap System Design Interview Evaluator.

Evaluate the candidate only from the provided mock interview transcript.
Return only valid JSON. No markdown.

Return JSON in this exact structure:

{
"overall_score": 0,
"summary": "",
"strengths": [""],
"gaps": [""],
"missed_topics": [""],
"better_answer_outline": [""],
"next_practice_steps": [""]
}

Scoring rules:
* overall_score must be a number from 0 to 100.
* Reward clear requirements clarification, API design, data modeling, architecture, scalability, reliability, observability, and tradeoff thinking.
* Penalize vague answers, missing bottlenecks, missing failure handling, and unsupported assumptions.
* If the transcript is too short to judge, give a low score and explain what was missing."""


def build_resume_match_prompt(job_description, resume_text):
    payload = {
        "job_description": job_description.strip(),
        "resume_text": resume_text.strip(),
    }
    return f"{ANALYZER_INSTRUCTIONS}\n\nInput:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"


def build_resume_match_payload(job_description, resume_text):
    return {
        "job_description": job_description.strip(),
        "resume_text": resume_text.strip(),
    }


def parse_analysis_json(raw_json):
    try:
        parsed_json = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"Please paste valid JSON. {exc.msg}") from exc

    return validate_analysis_payload(parsed_json)


def validate_analysis_payload(parsed_json):
    if not isinstance(parsed_json, dict):
        raise ValidationError("The analysis result must be a JSON object.")

    status = parsed_json.get("status")
    if status not in ("success", "refused"):
        raise ValidationError('The JSON must include status as either "success" or "refused".')

    if status == "refused":
        if not isinstance(parsed_json.get("reason"), str) or not parsed_json["reason"].strip():
            raise ValidationError('Refused analysis JSON must include a non-empty "reason".')
        return parsed_json

    required_strings = (
        "match_level",
        "final_recommendation",
    )
    required_objects = (
        "ats_compatibility",
        "application_confidence",
        "summary",
    )
    required_arrays = (
        "strengths",
        "missing_keywords",
        "matched_skills",
        "gaps_or_risks",
    )

    if "overall_match_score" not in parsed_json:
        raise ValidationError('Analysis JSON must include "overall_match_score".')
    _validate_score(parsed_json["overall_match_score"], "overall_match_score")

    for field in required_strings:
        if not isinstance(parsed_json.get(field), str) or not parsed_json[field].strip():
            raise ValidationError(f'Analysis JSON must include a non-empty "{field}".')

    for field in required_objects:
        if not isinstance(parsed_json.get(field), dict):
            raise ValidationError(f'Analysis JSON must include "{field}" as an object.')

    for field in required_arrays:
        if not isinstance(parsed_json.get(field), list):
            raise ValidationError(f'Analysis JSON must include "{field}" as a list.')

    _validate_score(parsed_json["ats_compatibility"].get("score"), "ats_compatibility.score")
    _validate_score(parsed_json["application_confidence"].get("score"), "application_confidence.score")

    for field in ("status",):
        if not isinstance(parsed_json["ats_compatibility"].get(field), str) or not parsed_json["ats_compatibility"][field].strip():
            raise ValidationError(f'Analysis JSON must include "ats_compatibility.{field}".')

    if not isinstance(parsed_json["application_confidence"].get("label"), str) or not parsed_json["application_confidence"]["label"].strip():
        raise ValidationError('Analysis JSON must include "application_confidence.label".')

    required_summary_fields = ("short_verdict", "candidate_positioning", "recruiter_likely_impression")
    for field in required_summary_fields:
        if not isinstance(parsed_json["summary"].get(field), str) or not parsed_json["summary"][field].strip():
            raise ValidationError(f'Analysis JSON must include "summary.{field}".')

    return parsed_json


def _validate_score(value, field_name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f'Analysis JSON must include "{field_name}" as a number from 0 to 100.')
    if value < 0 or value > 100:
        raise ValidationError(f'Analysis JSON must include "{field_name}" as a number from 0 to 100.')


def build_mock_interview_instructions(topic, level):
    return f"""You are a realistic system design interviewer for HackerLeap.

Interview topic:
{topic}

Candidate level:
{level}

Run a live mock system design interview. Follow these rules:
1. Converse only in English, even if the candidate uses another language.
2. Act like an interviewer, not a tutor or solution explainer.
3. Ask one question at a time.
4. Start by asking the candidate to clarify requirements.
5. Probe functional requirements, non-functional requirements, APIs, data model, high-level architecture, scaling, caching, consistency, reliability, observability, failure handling, and tradeoffs.
6. Do not reveal the full answer, suggested architecture, or detailed solution unless the candidate explicitly asks for help.
7. If the candidate asks for help, give a small hint or nudge, then return to interviewing.
8. If the candidate explicitly asks for help, give a small hint immediately and return to interviewing.
9. Otherwise, wait for the candidate to pause for about 20 seconds before giving a brief nudge, follow-up question, or redirect.
10. Keep responses concise and natural, like a real interviewer.
11. Avoid giving a final score during the voice session.
12. Continue until the candidate ends the interview."""


def create_mock_interview_realtime_token(user, session):
    if not settings.OPENAI_API_KEY:
        raise ImproperlyConfigured("OPENAI_API_KEY is required for mock voice interviews.")

    safety_identifier = hashlib.sha256(f"hackerleap-user-{user.id}".encode("utf-8")).hexdigest()
    payload = {
        "session": {
            "type": "realtime",
            "model": settings.OPENAI_REALTIME_MODEL,
            "instructions": build_mock_interview_instructions(session.topic, session.get_level_display()),
            "audio": {
                "input": {
                    "transcription": {
                        "model": settings.OPENAI_REALTIME_TRANSCRIPTION_MODEL,
                    },
                    "turn_detection": {
                        "type": "server_vad",
                        "create_response": False,
                    },
                },
                "output": {
                    "voice": settings.OPENAI_REALTIME_VOICE,
                },
            },
        }
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/realtime/client_secrets",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json",
            "OpenAI-Safety-Identifier": safety_identifier,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ValidationError(f"Unable to create voice interview session. OpenAI returned {exc.code}: {detail[:240]}") from exc
    except urllib.error.URLError as exc:
        raise ValidationError("Unable to reach OpenAI for voice interview setup. Please try again.") from exc


def generate_mock_interview_feedback(session):
    if not settings.OPENAI_API_KEY:
        raise ImproperlyConfigured("OPENAI_API_KEY is required for mock interview feedback.")

    transcript = session.transcript_text.strip()
    if not transcript:
        transcript = "\n".join(f"{turn.get_role_display()}: {turn.text}" for turn in session.turns.all())

    from openai import OpenAI

    response = OpenAI(api_key=settings.OPENAI_API_KEY).chat.completions.create(
        model=settings.OPENAI_FEEDBACK_MODEL,
        messages=[
            {"role": "system", "content": MOCK_INTERVIEW_FEEDBACK_INSTRUCTIONS},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "topic": session.topic,
                        "level": session.get_level_display(),
                        "transcript": transcript,
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content
    return parse_mock_interview_feedback_json(content)


def parse_mock_interview_feedback_json(raw_json):
    try:
        parsed_json = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"Mock interview feedback must be valid JSON. {exc.msg}") from exc

    if not isinstance(parsed_json, dict):
        raise ValidationError("Mock interview feedback must be a JSON object.")

    _validate_score(parsed_json.get("overall_score"), "overall_score")
    if not isinstance(parsed_json.get("summary"), str) or not parsed_json["summary"].strip():
        raise ValidationError('Mock interview feedback must include non-empty "summary".')

    for field in ("strengths", "gaps", "missed_topics", "better_answer_outline", "next_practice_steps"):
        if not isinstance(parsed_json.get(field), list):
            raise ValidationError(f'Mock interview feedback must include "{field}" as a list.')

    return parsed_json


@dataclass(frozen=True)
class ResumeMatchResult:
    generated_prompt: str
    ai_response_json: dict | None
    provider: str

    @property
    def is_complete(self):
        return self.ai_response_json is not None


class ResumeMatchAIClient:
    provider_name = "base"

    def analyze(self, *, job_description, resume_text):
        raise NotImplementedError


class ManualResumeMatchClient(ResumeMatchAIClient):
    provider_name = "manual"

    def analyze(self, *, job_description, resume_text):
        return ResumeMatchResult(
            generated_prompt=build_resume_match_prompt(job_description, resume_text),
            ai_response_json=None,
            provider=self.provider_name,
        )


class ChatGPTResumeMatchClient(ResumeMatchAIClient):
    provider_name = "chatgpt"

    def __init__(self, *, api_key=None, model=None):
        self.api_key = api_key if api_key is not None else settings.OPENAI_API_KEY
        self.model = model if model is not None else settings.OPENAI_MODEL

    def analyze(self, *, job_description, resume_text):
        if not self.api_key:
            raise ImproperlyConfigured("OPENAI_API_KEY is required when HACKERLEAP_AI_MODE=chatgpt.")

        from openai import OpenAI

        payload = build_resume_match_payload(job_description, resume_text)
        response = OpenAI(api_key=self.api_key).chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": ANALYZER_INSTRUCTIONS},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        return ResumeMatchResult(
            generated_prompt=build_resume_match_prompt(job_description, resume_text),
            ai_response_json=parse_analysis_json(content),
            provider=self.provider_name,
        )


class ClaudeResumeMatchClient(ResumeMatchAIClient):
    provider_name = "claude"

    def analyze(self, *, job_description, resume_text):
        raise NotImplementedError("Claude resume match analysis integration is not implemented yet.")


def get_resume_match_client(mode=None):
    selected_mode = normalize_resume_analysis_mode(mode or settings.HACKERLEAP_AI_MODE)
    clients = {
        ManualResumeMatchClient.provider_name: ManualResumeMatchClient,
        ChatGPTResumeMatchClient.provider_name: ChatGPTResumeMatchClient,
        ClaudeResumeMatchClient.provider_name: ClaudeResumeMatchClient,
    }
    try:
        return clients[selected_mode]()
    except KeyError as exc:
        raise ImproperlyConfigured(f"Unsupported HACKERLEAP_AI_MODE: {selected_mode}") from exc


def run_resume_match_analysis(*, job_description, resume_text, mode=None):
    return get_resume_match_client(mode=mode).analyze(
        job_description=job_description,
        resume_text=resume_text,
    )


def normalize_resume_analysis_mode(mode):
    return (mode or "manual").strip().lower()


def get_user_feature_flags(user, *, create=False):
    from .models import UserFeatureFlags

    if create:
        feature_flags, _ = UserFeatureFlags.objects.get_or_create(user=user)
        return feature_flags

    return UserFeatureFlags.objects.filter(user=user).first()


def user_has_coding_platform_access(user):
    if not user or not user.is_authenticated or not user.is_active:
        return False
    if user.is_staff:
        return True
    feature_flags = get_user_feature_flags(user)
    return bool(feature_flags and feature_flags.can_access_coding_platform)


def get_configured_resume_analysis_mode(user):
    feature_flags = get_user_feature_flags(user)
    user_mode = feature_flags.ai_mode if feature_flags and feature_flags.ai_mode else None
    return normalize_resume_analysis_mode(user_mode or settings.HACKERLEAP_AI_MODE)


def get_effective_resume_analysis_mode(user):
    configured_mode = get_configured_resume_analysis_mode(user)
    if configured_mode not in {"chatgpt", "claude"}:
        return configured_mode

    feature_flags = get_user_feature_flags(user)
    if not feature_flags:
        return configured_mode

    if feature_flags.can_run_ai_analysis():
        return configured_mode

    return "manual"


def reserve_resume_analysis_ai_quota(user):
    configured_mode = get_configured_resume_analysis_mode(user)
    if configured_mode not in {"chatgpt", "claude"}:
        return False

    feature_flags = get_user_feature_flags(user, create=True)
    return feature_flags.consume_ai_analysis_quota()


def reserve_mock_interview_quota(user):
    feature_flags = get_user_feature_flags(user, create=True)
    return feature_flags.consume_mock_interview_quota()

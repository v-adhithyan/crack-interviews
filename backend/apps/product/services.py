import json

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
    selected_mode = (mode or settings.HACKERLEAP_AI_MODE or "manual").strip().lower()
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

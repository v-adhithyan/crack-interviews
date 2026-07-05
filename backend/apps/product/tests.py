import json
import shutil
import tempfile

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.website.models import EarlyAccessUser

from .models import Resume
from .models import ResumeAnalysis
from .models import ResumeAnalysisSettings
from .models import MockInterviewSession
from .models import MockInterviewTurn
from .services import ResumeMatchResult
from .services import build_mock_interview_instructions
from .services import parse_mock_interview_feedback_json
from .tasks import run_resume_analysis


class ProductAccessTests(TestCase):
    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse("product_dashboard"))

        self.assertRedirects(response, f"{reverse('login')}?next={reverse('product_dashboard')}")

    def test_staff_user_can_access_product_dashboard(self):
        user = get_user_model().objects.create_user(
            username="staff",
            email="staff@example.com",
            password="Password1!",
            is_staff=True,
        )
        self.client.force_login(user)

        response = self.client.get(reverse("product_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Upload Your Resume")

    def test_regular_user_without_active_beta_access_is_forbidden(self):
        user = get_user_model().objects.create_user(
            username="regular@example.com",
            email="regular@example.com",
            password="Password1!",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("product_dashboard"))

        self.assertEqual(response.status_code, 403)

    def test_active_beta_user_can_access_product_dashboard(self):
        user = get_user_model().objects.create_user(
            username="active@example.com",
            email="active@example.com",
            password="Password1!",
        )
        EarlyAccessUser.objects.create(email=user.email, user=user, is_beta_active=True, signup_completed_at=timezone.now())
        self.client.force_login(user)

        response = self.client.get(reverse("product_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Recent Analysis")

    @override_settings(HACKERLEAP_CODE="http://localhost:3000")
    def test_staff_user_can_redirect_to_code_platform(self):
        user = get_user_model().objects.create_user(
            username="staff-code",
            email="staff-code@example.com",
            password="Password1!",
            is_staff=True,
        )
        self.client.force_login(user)

        response = self.client.get(reverse("code_platform_redirect"))

        self.assertRedirects(response, "http://localhost:3000", fetch_redirect_response=False)

    @override_settings(HACKERLEAP_CODE="https://code.hackerleap.com")
    def test_beta_user_with_coding_flag_can_redirect_to_code_platform(self):
        user = get_user_model().objects.create_user(
            username="coder@example.com",
            email="coder@example.com",
            password="Password1!",
        )
        EarlyAccessUser.objects.create(email=user.email, user=user, is_beta_active=True, signup_completed_at=timezone.now())
        ResumeAnalysisSettings.objects.create(user=user, can_access_coding_platform=True)
        self.client.force_login(user)

        response = self.client.get(reverse("code_platform_redirect"))

        self.assertRedirects(response, "https://code.hackerleap.com", fetch_redirect_response=False)

    def test_beta_user_without_coding_flag_is_redirected_to_dashboard(self):
        user = get_user_model().objects.create_user(
            username="blocked-code@example.com",
            email="blocked-code@example.com",
            password="Password1!",
        )
        EarlyAccessUser.objects.create(email=user.email, user=user, is_beta_active=True, signup_completed_at=timezone.now())
        self.client.force_login(user)

        response = self.client.get(reverse("code_platform_redirect"))

        self.assertRedirects(response, reverse("product_dashboard"))


class MockInterviewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="mock@example.com",
            email="mock@example.com",
            password="Password1!",
        )
        EarlyAccessUser.objects.create(email=self.user.email, user=self.user, is_beta_active=True, signup_completed_at=timezone.now())
        self.client.force_login(self.user)

    def test_start_page_is_accessible_to_beta_user(self):
        response = self.client.get(reverse("mock_interview_start"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mock system design interview")
        self.assertContains(response, "URL Shortener")
        self.assertContains(response, "Custom question")

    def test_create_preset_interview_session(self):
        response = self.client.post(
            reverse("mock_interview_create"),
            {
                "preset_topic": "Rate Limiter",
                "custom_topic": "",
                "level": MockInterviewSession.Level.SENIOR,
            },
        )

        session = MockInterviewSession.objects.get(user=self.user)
        self.assertRedirects(response, reverse("mock_interview_room", kwargs={"session_uuid": session.uuid}))
        self.assertEqual(session.topic_source, MockInterviewSession.TopicSource.PRESET)
        self.assertEqual(session.topic, "Rate Limiter")
        self.assertEqual(session.level, MockInterviewSession.Level.SENIOR)

    def test_custom_question_takes_precedence_over_preset_topic(self):
        response = self.client.post(
            reverse("mock_interview_create"),
            {
                "preset_topic": "URL Shortener",
                "custom_topic": "Design a real-time stock alerting platform.",
                "level": MockInterviewSession.Level.STAFF,
            },
        )

        session = MockInterviewSession.objects.get(user=self.user)
        self.assertRedirects(response, reverse("mock_interview_room", kwargs={"session_uuid": session.uuid}))
        self.assertEqual(session.topic_source, MockInterviewSession.TopicSource.CUSTOM)
        self.assertEqual(session.topic, "Design a real-time stock alerting platform.")
        self.assertEqual(session.level, MockInterviewSession.Level.STAFF)

    def test_custom_question_max_length_is_validated(self):
        response = self.client.post(
            reverse("mock_interview_create"),
            {
                "preset_topic": "URL Shortener",
                "custom_topic": "x" * 1001,
                "level": MockInterviewSession.Level.SENIOR,
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(MockInterviewSession.objects.filter(user=self.user).exists())
        self.assertContains(response, "Please keep the custom question under 1,000 characters", status_code=400)

    def test_room_exposes_sixty_minute_timer_data(self):
        session = MockInterviewSession.objects.create(user=self.user, topic="URL Shortener")

        response = self.client.get(reverse("mock_interview_room", kwargs={"session_uuid": session.uuid}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-duration-seconds="3600"')
        self.assertContains(response, "60:00")

    def test_active_room_loads_as_paused_resume_state(self):
        session = MockInterviewSession.objects.create(
            user=self.user,
            topic="URL Shortener",
            status=MockInterviewSession.Status.ACTIVE,
            started_at=timezone.now() - timedelta(minutes=5),
        )

        response = self.client.get(reverse("mock_interview_room", kwargs={"session_uuid": session.uuid}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-session-status="active"')
        self.assertContains(response, "Resume Interview")
        self.assertContains(response, "Session paused in this browser")

    def test_mock_interview_instructions_include_resume_transcript_context(self):
        instructions = build_mock_interview_instructions(
            "URL Shortener",
            "Senior",
            "Interviewer: What scale should we design for?\nUser: Ten million daily active users.",
        )

        self.assertIn("Conversation so far before this realtime connection was created", instructions)
        self.assertIn("Ten million daily active users", instructions)
        self.assertIn("Do not restart the interview", instructions)

    @override_settings(OPENAI_API_KEY="test-key")
    def test_token_endpoint_consumes_quota_and_returns_payload(self):
        session = MockInterviewSession.objects.create(
            user=self.user,
            topic="URL Shortener",
            level=MockInterviewSession.Level.SENIOR,
        )

        with patch("apps.product.views.create_mock_interview_realtime_token", return_value={"value": "ephemeral-token"}):
            response = self.client.post(reverse("mock_interview_token", kwargs={"session_uuid": session.uuid}))

        session.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["value"], "ephemeral-token")
        self.assertEqual(session.status, MockInterviewSession.Status.ACTIVE)
        self.assertIsNotNone(session.started_at)
        self.assertEqual(self.user.feature_flags.mock_interview_count, 1)

    def test_token_endpoint_rejects_exhausted_quota(self):
        feature_flags = ResumeAnalysisSettings.objects.create(
            user=self.user,
            mock_interview_daily_limit=1,
            mock_interview_count=1,
            mock_interview_window_started_at=timezone.now(),
        )
        session = MockInterviewSession.objects.create(user=self.user, topic="Chat Application")

        response = self.client.post(reverse("mock_interview_token", kwargs={"session_uuid": session.uuid}))

        feature_flags.refresh_from_db()
        session.refresh_from_db()
        self.assertEqual(response.status_code, 429)
        self.assertEqual(feature_flags.mock_interview_count, 1)
        self.assertEqual(session.status, MockInterviewSession.Status.CREATED)

    def test_token_endpoint_rejects_expired_active_interview(self):
        session = MockInterviewSession.objects.create(
            user=self.user,
            topic="URL Shortener",
            status=MockInterviewSession.Status.ACTIVE,
            started_at=timezone.now() - timedelta(minutes=61),
        )

        response = self.client.post(reverse("mock_interview_token", kwargs={"session_uuid": session.uuid}))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "This interview has reached the 60 minute time limit.")

    def test_turn_endpoint_saves_transcript_turn(self):
        session = MockInterviewSession.objects.create(user=self.user, topic="Notification System")

        response = self.client.post(
            reverse("mock_interview_turns", kwargs={"session_uuid": session.uuid}),
            data=json.dumps({"role": "assistant", "text": "What are the core requirements?"}),
            content_type="application/json",
        )

        session.refresh_from_db()
        turn = MockInterviewTurn.objects.get(session=session)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(turn.role, MockInterviewTurn.Role.INTERVIEWER)
        self.assertIn("Interviewer: What are the core requirements?", session.transcript_text)

    def test_other_users_cannot_access_session(self):
        other_user = get_user_model().objects.create_user(username="other@example.com", email="other@example.com", password="Password1!")
        EarlyAccessUser.objects.create(email=other_user.email, user=other_user, is_beta_active=True, signup_completed_at=timezone.now())
        session = MockInterviewSession.objects.create(user=other_user, topic="File Storage Service")

        response = self.client.get(reverse("mock_interview_room", kwargs={"session_uuid": session.uuid}))

        self.assertEqual(response.status_code, 404)

    def test_staff_can_access_other_users_session(self):
        staff = get_user_model().objects.create_user(username="staff-mock", email="staff-mock@example.com", password="Password1!", is_staff=True)
        session = MockInterviewSession.objects.create(user=self.user, topic="Food Delivery App")
        self.client.force_login(staff)

        response = self.client.get(reverse("mock_interview_room", kwargs={"session_uuid": session.uuid}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Food Delivery App")

    def test_mock_interview_quota_resets_after_24_hours(self):
        feature_flags = ResumeAnalysisSettings.objects.create(
            user=self.user,
            mock_interview_daily_limit=1,
            mock_interview_count=1,
            mock_interview_window_started_at=timezone.now() - timedelta(hours=25),
        )

        self.assertTrue(feature_flags.can_run_mock_interview())
        feature_flags.refresh_from_db()
        self.assertEqual(feature_flags.mock_interview_count, 0)
        self.assertIsNone(feature_flags.mock_interview_window_started_at)

    def test_finish_endpoint_generates_feedback(self):
        session = MockInterviewSession.objects.create(user=self.user, topic="URL Shortener")
        MockInterviewTurn.objects.create(session=session, role=MockInterviewTurn.Role.USER, text="I would clarify scale first.")
        feedback = {
            "overall_score": 72,
            "summary": "Solid clarification start.",
            "strengths": ["Clarified scale."],
            "gaps": ["Needs deeper storage design."],
            "missed_topics": ["Caching"],
            "better_answer_outline": ["Clarify requirements.", "Define APIs."],
            "next_practice_steps": ["Practice data modeling."],
        }

        with patch("apps.product.views.generate_mock_interview_feedback", return_value=feedback):
            response = self.client.post(reverse("mock_interview_finish", kwargs={"session_uuid": session.uuid}))

        session.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(session.status, MockInterviewSession.Status.COMPLETED)
        self.assertEqual(session.feedback_json["overall_score"], 72)
        self.assertEqual(response.json()["feedback_url"], reverse("mock_interview_feedback", kwargs={"session_uuid": session.uuid}))

    def test_parse_mock_interview_feedback_json_validates_score(self):
        with self.assertRaises(Exception):
            parse_mock_interview_feedback_json(json.dumps({"overall_score": 101, "summary": "Bad", "strengths": [], "gaps": [], "missed_topics": [], "better_answer_outline": [], "next_practice_steps": []}))


class ResumeUploadTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_media_root = tempfile.mkdtemp()
        cls.override = override_settings(MEDIA_ROOT=cls.test_media_root)
        cls.override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.override.disable()
        shutil.rmtree(cls.test_media_root, ignore_errors=True)

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="resume@example.com",
            email="resume@example.com",
            password="Password1!",
        )
        EarlyAccessUser.objects.create(email=self.user.email, user=self.user, is_beta_active=True, signup_completed_at=timezone.now())
        self.client.force_login(self.user)

    def create_resume(self, user=None):
        user = user or self.user
        return Resume.objects.create(
            user=user,
            file=SimpleUploadedFile("resume.pdf", b"%PDF-1.4\nresume\n%%EOF", content_type="application/pdf"),
            original_filename="resume.pdf",
            content_type="application/pdf",
            size=24,
            parsed_text="Python Django resume.",
        )

    def create_analysis(self, user=None, resume=None, **overrides):
        user = user or self.user
        resume = resume or self.create_resume(user)
        payload = {
            "status": "success",
            "role_title_detected": "Senior Backend Engineer",
            "company_detected": "TechNova Inc.",
            "overall_match_score": 82,
            "match_level": "Strong",
            "ats_compatibility": {"score": 78, "status": "Good", "summary": "Clear backend match."},
            "summary": {
                "short_verdict": "Strong fit.",
                "candidate_positioning": "Backend engineer.",
                "recruiter_likely_impression": "Relevant experience.",
            },
            "strengths": [{"title": "Python", "evidence_from_resume": "Built APIs.", "relevance_to_job": "Core skill."}],
            "missing_keywords": [{"keyword": "Kubernetes", "importance": "Medium", "reason": "Not explicit."}],
            "matched_skills": [{"skill": "Django", "evidence_from_resume": "Built Django APIs."}],
            "gaps_or_risks": [{"gap": "Cloud", "why_it_matters": "Role mentions cloud.", "suggested_fix": "Add cloud work."}],
            "resume_improvement_suggestions": [
                {
                    "section": "Experience",
                    "current_issue": "Impact is described without numbers.",
                    "suggested_change": "Add quantified latency and reliability improvements.",
                    "reason": "Metrics make the backend impact easier to evaluate.",
                }
            ],
            "rewritten_bullets": [
                {
                    "original_bullet": "Built Django APIs.",
                    "improved_bullet": "Built Django APIs that reduced request latency by 35%.",
                    "why_better": "Adds measurable impact and keeps the technical context.",
                }
            ],
            "recommended_keywords_to_add_naturally": ["System Design", "Kubernetes"],
            "application_confidence": {"score": 80, "label": "High", "reason": "Good overlap."},
            "final_recommendation": "Apply with tailored keywords.",
        }
        ai_response_json = overrides.pop("ai_response_json", payload)
        if isinstance(ai_response_json, dict) and ai_response_json is not payload:
            payload.update(ai_response_json)
            ai_response_json = payload
        return ResumeAnalysis.objects.create(
            user=user,
            resume=resume,
            job_description=overrides.pop("job_description", "Python backend role."),
            resume_text=overrides.pop("resume_text", "Python Django resume."),
            generated_prompt=overrides.pop("generated_prompt", "Formatted prompt."),
            ai_response_json=ai_response_json,
            status=overrides.pop("status", ResumeAnalysis.Status.RESULT_ADDED),
            task_id=overrides.pop("task_id", ""),
            ai_provider=overrides.pop("ai_provider", ""),
            error_message=overrides.pop("error_message", ""),
        )

    def test_dashboard_shows_empty_resume_state(self):
        response = self.client.get(reverse("product_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-menu-toggle')
        self.assertContains(response, 'class="user-menu"')
        self.assertContains(response, ">Logout<")
        self.assertContains(response, "Choose your resume PDF")
        self.assertContains(response, "Select PDF")
        self.assertContains(response, reverse("current_resume_content"))
        self.assertContains(response, "favicon.svg")
        self.assertContains(response, "No analyses yet")
        self.assertNotContains(response, "Ankit_Resume.pdf")

    def test_pdf_resume_upload_creates_resume_for_user(self):
        resume_file = SimpleUploadedFile(
            "adhi_resume.pdf",
            b"%PDF-1.4\nresume\n%%EOF",
            content_type="application/pdf",
        )

        with patch("apps.product.forms.extract_pdf_text", return_value="Parsed resume text."):
            response = self.client.post(reverse("product_dashboard"), {"resume": resume_file}, follow=True)

        resume = Resume.objects.get(user=self.user)
        self.assertRedirects(response, reverse("product_dashboard"))
        self.assertEqual(resume.original_filename, "adhi_resume.pdf")
        self.assertEqual(resume.content_type, "application/pdf")
        self.assertEqual(resume.parsed_text, "Parsed resume text.")
        self.assertContains(response, "adhi_resume.pdf")
        self.assertContains(response, reverse("resume_content", kwargs={"resume_uuid": resume.uuid}))
        self.assertContains(response, 'target="_blank"')
        self.assertContains(response, "Start New Analysis")
        self.assertNotContains(response, "Choose your resume PDF")

    def test_pdf_resume_without_readable_text_is_rejected(self):
        resume_file = SimpleUploadedFile(
            "scanned_resume.pdf",
            b"%PDF-1.4\nresume\n%%EOF",
            content_type="application/pdf",
        )

        with patch("apps.product.forms.extract_pdf_text", return_value=""):
            response = self.client.post(reverse("product_dashboard"), {"resume": resume_file})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Resume.objects.filter(user=self.user).exists())
        self.assertContains(response, "We could not find readable text in this PDF.")

    def test_non_pdf_resume_is_rejected(self):
        resume_file = SimpleUploadedFile(
            "resume.txt",
            b"not a pdf",
            content_type="text/plain",
        )

        response = self.client.post(reverse("product_dashboard"), {"resume": resume_file})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Resume.objects.filter(user=self.user).exists())
        self.assertContains(response, "Please upload a PDF resume.")

    def test_resume_larger_than_one_mb_is_rejected(self):
        resume_file = SimpleUploadedFile(
            "large_resume.pdf",
            b"x" * (1024 * 1024 + 1),
            content_type="application/pdf",
        )

        response = self.client.post(reverse("product_dashboard"), {"resume": resume_file})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Resume.objects.filter(user=self.user).exists())
        self.assertContains(response, "Please upload a PDF no larger than 1 MB.")

    def test_upload_replaces_existing_resume_for_user(self):
        first_file = SimpleUploadedFile("first.pdf", b"%PDF-1.4\nfirst\n%%EOF", content_type="application/pdf")
        second_file = SimpleUploadedFile("second.pdf", b"%PDF-1.4\nsecond\n%%EOF", content_type="application/pdf")

        with patch("apps.product.forms.extract_pdf_text", return_value="First resume text."):
            self.client.post(reverse("product_dashboard"), {"resume": first_file})
        first_uuid = Resume.objects.get(user=self.user).uuid
        with patch("apps.product.forms.extract_pdf_text", return_value="Second resume text."):
            self.client.post(reverse("product_dashboard"), {"resume": second_file})
        resume = Resume.objects.get(user=self.user)

        self.assertEqual(Resume.objects.filter(user=self.user).count(), 1)
        self.assertEqual(resume.original_filename, "second.pdf")
        self.assertEqual(resume.parsed_text, "Second resume text.")
        self.assertNotEqual(resume.uuid, first_uuid)
        self.assertEqual(self.client.get(reverse("resume_content", kwargs={"resume_uuid": first_uuid})).status_code, 404)

    def test_uploaded_resume_filename_has_tooltip(self):
        long_name = "adhithyan_vijayakumar_backend_engineer_resume_2026_final.pdf"
        resume_file = SimpleUploadedFile(long_name, b"%PDF-1.4\nresume\n%%EOF", content_type="application/pdf")
        with patch("apps.product.forms.extract_pdf_text", return_value="Parsed resume text."):
            self.client.post(reverse("product_dashboard"), {"resume": resume_file})

        response = self.client.get(reverse("product_dashboard"))

        self.assertContains(response, 'class="filename-with-tooltip"', count=2)
        self.assertContains(response, f'title="{long_name}"', count=2)
        self.assertContains(response, f'data-tooltip="{long_name}"', count=2)

    def test_user_can_view_own_resume_content_with_private_cache_headers(self):
        resume_file = SimpleUploadedFile("own.pdf", b"%PDF-1.4\nown\n%%EOF", content_type="application/pdf")
        with patch("apps.product.forms.extract_pdf_text", return_value="Parsed resume text."):
            self.client.post(reverse("product_dashboard"), {"resume": resume_file})
        resume = Resume.objects.get(user=self.user)

        response = self.client.get(reverse("resume_content", kwargs={"resume_uuid": resume.uuid}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertEqual(response["Cache-Control"], "private, max-age=31536000, immutable")
        self.assertEqual(response["ETag"], f'"resume-{resume.uuid}"')
        self.assertIn("inline", response["Content-Disposition"])
        self.assertEqual(b"".join(response.streaming_content), b"%PDF-1.4\nown\n%%EOF")

    def test_current_resume_link_returns_404_when_user_has_no_resume(self):
        response = self.client.get(reverse("current_resume_content"))

        self.assertEqual(response.status_code, 404)

    def test_current_resume_link_serves_users_uploaded_resume(self):
        resume_file = SimpleUploadedFile("own.pdf", b"%PDF-1.4\nown\n%%EOF", content_type="application/pdf")
        with patch("apps.product.forms.extract_pdf_text", return_value="Parsed resume text."):
            self.client.post(reverse("product_dashboard"), {"resume": resume_file})

        response = self.client.get(reverse("current_resume_content"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("inline", response["Content-Disposition"])
        self.assertEqual(b"".join(response.streaming_content), b"%PDF-1.4\nown\n%%EOF")

    def test_user_cannot_view_another_users_resume_content(self):
        other_user = get_user_model().objects.create_user(
            username="other@example.com",
            email="other@example.com",
            password="Password1!",
        )
        resume = Resume.objects.create(
            user=other_user,
            file=SimpleUploadedFile("other.pdf", b"%PDF-1.4\nother\n%%EOF", content_type="application/pdf"),
            original_filename="other.pdf",
            content_type="application/pdf",
            size=22,
        )

        response = self.client.get(reverse("resume_content", kwargs={"resume_uuid": resume.uuid}))

        self.assertEqual(response.status_code, 404)

    def test_staff_can_view_any_resume_content(self):
        other_user = get_user_model().objects.create_user(
            username="other@example.com",
            email="other@example.com",
            password="Password1!",
        )
        staff_user = get_user_model().objects.create_user(
            username="staff-viewer",
            email="staff-viewer@example.com",
            password="Password1!",
            is_staff=True,
        )
        resume = Resume.objects.create(
            user=other_user,
            file=SimpleUploadedFile("other.pdf", b"%PDF-1.4\nother\n%%EOF", content_type="application/pdf"),
            original_filename="other.pdf",
            content_type="application/pdf",
            size=22,
        )
        self.client.force_login(staff_user)

        response = self.client.get(reverse("resume_content", kwargs={"resume_uuid": resume.uuid}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), b"%PDF-1.4\nother\n%%EOF")

    @override_settings(HACKERLEAP_AI_MODE="manual")
    def test_analyze_now_generates_manual_prompt(self):
        resume_file = SimpleUploadedFile("resume.pdf", b"%PDF-1.4\nresume\n%%EOF", content_type="application/pdf")
        with patch("apps.product.forms.extract_pdf_text", return_value="Built Django APIs and Python services."):
            self.client.post(reverse("product_dashboard"), {"resume": resume_file})

        response = self.client.post(
            reverse("product_dashboard"),
            {
                "action": "generate_prompt",
                "job_description": "We need a Python Django backend engineer.",
            },
            follow=True,
        )

        analysis = ResumeAnalysis.objects.get(user=self.user)
        self.assertRedirects(response, reverse("product_dashboard"))
        self.assertContains(response, "Formatted Prompt")
        self.assertContains(response, "HackerLeap Resume Match Analyzer")
        self.assertContains(response, "We need a Python Django backend engineer.")
        self.assertIn('"job_description": "We need a Python Django backend engineer."', analysis.generated_prompt)
        self.assertIn('"resume_text": "Built Django APIs and Python services."', analysis.generated_prompt)

    @override_settings(HACKERLEAP_AI_MODE="manual")
    def test_job_description_over_server_limit_is_rejected(self):
        resume_file = SimpleUploadedFile("resume.pdf", b"%PDF-1.4\nresume\n%%EOF", content_type="application/pdf")
        with patch("apps.product.forms.extract_pdf_text", return_value="Built Django APIs and Python services."):
            self.client.post(reverse("product_dashboard"), {"resume": resume_file})

        response = self.client.post(
            reverse("product_dashboard"),
            {
                "action": "generate_prompt",
                "job_description": "x" * 12001,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(ResumeAnalysis.objects.filter(user=self.user).exists())
        self.assertContains(response, "Please keep the job description under 12,000 characters.")

    @override_settings(HACKERLEAP_AI_MODE="chatgpt")
    def test_chatgpt_mode_queues_ai_analysis_and_redirects_to_progress(self):
        resume_file = SimpleUploadedFile("resume.pdf", b"%PDF-1.4\nresume\n%%EOF", content_type="application/pdf")
        with patch("apps.product.forms.extract_pdf_text", return_value="Built Django APIs and Python services."):
            self.client.post(reverse("product_dashboard"), {"resume": resume_file})

        with patch("apps.product.views.enqueue_background_job", return_value="task-123") as enqueue_job:
            response = self.client.post(
                reverse("product_dashboard"),
                {
                    "action": "generate_prompt",
                    "job_description": "We need a Python Django backend engineer.",
                },
                follow=True,
            )

        analysis = ResumeAnalysis.objects.get(user=self.user)
        enqueue_job.assert_called_once_with("apps.product.tasks.run_resume_analysis", analysis.id)
        self.assertRedirects(response, reverse("analysis_detail", kwargs={"analysis_uuid": analysis.uuid}))
        self.assertEqual(analysis.status, ResumeAnalysis.Status.QUEUED)
        self.assertEqual(analysis.task_id, "task-123")
        self.assertEqual(analysis.ai_provider, "chatgpt")
        self.assertIsNone(analysis.ai_response_json)
        self.assertContains(response, "Queued for analysis")
        self.assertContains(response, "Analysis queued.")

    @override_settings(HACKERLEAP_AI_MODE="chatgpt")
    def test_ai_analysis_limit_falls_back_to_manual_after_two_uses(self):
        resume_file = SimpleUploadedFile("resume.pdf", b"%PDF-1.4\nresume\n%%EOF", content_type="application/pdf")
        with patch("apps.product.forms.extract_pdf_text", return_value="Built Django APIs and Python services."):
            self.client.post(reverse("product_dashboard"), {"resume": resume_file})

        with patch("apps.product.views.enqueue_background_job", side_effect=["task-1", "task-2"]) as enqueue_job:
            for index in range(3):
                response = self.client.post(
                    reverse("product_dashboard"),
                    {
                        "action": "generate_prompt",
                        "job_description": f"We need a Python Django backend engineer {index}.",
                    },
                    follow=True,
                )

        analyses = list(ResumeAnalysis.objects.filter(user=self.user).order_by("created_at"))
        feature_flags = ResumeAnalysisSettings.objects.get(user=self.user)
        self.assertEqual(enqueue_job.call_count, 2)
        self.assertEqual([analysis.status for analysis in analyses], [ResumeAnalysis.Status.QUEUED, ResumeAnalysis.Status.QUEUED, ResumeAnalysis.Status.PROMPT_READY])
        self.assertEqual([analysis.ai_provider for analysis in analyses], ["chatgpt", "chatgpt", "manual"])
        self.assertEqual(feature_flags.ai_analysis_count, 2)
        self.assertContains(response, "Daily AI analysis limit reached.")

    @override_settings(HACKERLEAP_AI_MODE="chatgpt")
    def test_ai_analysis_limit_resets_after_twenty_four_hours(self):
        ResumeAnalysisSettings.objects.create(
            user=self.user,
            ai_analysis_count=2,
            ai_analysis_window_started_at=timezone.now() - timedelta(hours=25),
        )
        resume_file = SimpleUploadedFile("resume.pdf", b"%PDF-1.4\nresume\n%%EOF", content_type="application/pdf")
        with patch("apps.product.forms.extract_pdf_text", return_value="Built Django APIs and Python services."):
            self.client.post(reverse("product_dashboard"), {"resume": resume_file})

        with patch("apps.product.views.enqueue_background_job", return_value="task-reset") as enqueue_job:
            response = self.client.post(
                reverse("product_dashboard"),
                {
                    "action": "generate_prompt",
                    "job_description": "We need a Python Django backend engineer.",
                },
                follow=True,
            )

        analysis = ResumeAnalysis.objects.get(user=self.user)
        feature_flags = ResumeAnalysisSettings.objects.get(user=self.user)
        enqueue_job.assert_called_once_with("apps.product.tasks.run_resume_analysis", analysis.id)
        self.assertRedirects(response, reverse("analysis_detail", kwargs={"analysis_uuid": analysis.uuid}))
        self.assertEqual(analysis.status, ResumeAnalysis.Status.QUEUED)
        self.assertEqual(analysis.ai_provider, "chatgpt")
        self.assertEqual(feature_flags.ai_analysis_count, 1)
        self.assertGreater(feature_flags.ai_analysis_window_started_at, timezone.now() - timedelta(minutes=1))

    @override_settings(HACKERLEAP_AI_MODE="manual")
    def test_user_analysis_mode_override_queues_when_global_mode_is_manual(self):
        ResumeAnalysisSettings.objects.create(user=self.user, ai_mode=ResumeAnalysisSettings.AIMode.CHATGPT)
        resume_file = SimpleUploadedFile("resume.pdf", b"%PDF-1.4\nresume\n%%EOF", content_type="application/pdf")
        with patch("apps.product.forms.extract_pdf_text", return_value="Built Django APIs and Python services."):
            self.client.post(reverse("product_dashboard"), {"resume": resume_file})

        with patch("apps.product.views.enqueue_background_job", return_value="task-override") as enqueue_job:
            response = self.client.post(
                reverse("product_dashboard"),
                {
                    "action": "generate_prompt",
                    "job_description": "We need a Python Django backend engineer.",
                },
                follow=True,
            )

        analysis = ResumeAnalysis.objects.get(user=self.user)
        enqueue_job.assert_called_once_with("apps.product.tasks.run_resume_analysis", analysis.id)
        self.assertRedirects(response, reverse("analysis_detail", kwargs={"analysis_uuid": analysis.uuid}))
        self.assertEqual(analysis.status, ResumeAnalysis.Status.QUEUED)
        self.assertEqual(analysis.ai_provider, "chatgpt")

    @override_settings(HACKERLEAP_AI_MODE="chatgpt")
    def test_user_analysis_mode_override_can_force_manual_mode(self):
        ResumeAnalysisSettings.objects.create(user=self.user, ai_mode=ResumeAnalysisSettings.AIMode.MANUAL)
        resume_file = SimpleUploadedFile("resume.pdf", b"%PDF-1.4\nresume\n%%EOF", content_type="application/pdf")
        with patch("apps.product.forms.extract_pdf_text", return_value="Built Django APIs and Python services."):
            self.client.post(reverse("product_dashboard"), {"resume": resume_file})

        with patch("apps.product.views.enqueue_background_job") as enqueue_job:
            response = self.client.post(
                reverse("product_dashboard"),
                {
                    "action": "generate_prompt",
                    "job_description": "We need a Python Django backend engineer.",
                },
                follow=True,
            )

        analysis = ResumeAnalysis.objects.get(user=self.user)
        enqueue_job.assert_not_called()
        self.assertRedirects(response, reverse("product_dashboard"))
        self.assertEqual(analysis.status, ResumeAnalysis.Status.PROMPT_READY)
        self.assertEqual(analysis.ai_provider, "manual")
        self.assertContains(response, "Formatted Prompt")

    @override_settings(HACKERLEAP_AI_MODE="manual")
    def test_null_user_analysis_mode_falls_back_to_global_mode(self):
        ResumeAnalysisSettings.objects.create(user=self.user, ai_mode=None)
        resume_file = SimpleUploadedFile("resume.pdf", b"%PDF-1.4\nresume\n%%EOF", content_type="application/pdf")
        with patch("apps.product.forms.extract_pdf_text", return_value="Built Django APIs and Python services."):
            self.client.post(reverse("product_dashboard"), {"resume": resume_file})

        with patch("apps.product.views.enqueue_background_job") as enqueue_job:
            response = self.client.post(
                reverse("product_dashboard"),
                {
                    "action": "generate_prompt",
                    "job_description": "We need a Python Django backend engineer.",
                },
                follow=True,
            )

        analysis = ResumeAnalysis.objects.get(user=self.user)
        enqueue_job.assert_not_called()
        self.assertRedirects(response, reverse("product_dashboard"))
        self.assertEqual(analysis.status, ResumeAnalysis.Status.PROMPT_READY)
        self.assertEqual(analysis.ai_provider, "manual")

    @override_settings(HACKERLEAP_AI_MODE="chatgpt")
    def test_chatgpt_mode_hides_manual_prompt_panels(self):
        self.create_analysis()

        response = self.client.get(reverse("product_dashboard"))

        self.assertNotContains(response, "Formatted Prompt")
        self.assertNotContains(response, "Paste Analysis JSON")
        self.assertContains(response, "Analysis Result")

    @override_settings(HACKERLEAP_AI_MODE="manual")
    def test_pasted_json_result_is_saved_and_rendered(self):
        resume_file = SimpleUploadedFile("resume.pdf", b"%PDF-1.4\nresume\n%%EOF", content_type="application/pdf")
        with patch("apps.product.forms.extract_pdf_text", return_value="Python backend resume."):
            self.client.post(reverse("product_dashboard"), {"resume": resume_file})
        self.client.post(
            reverse("product_dashboard"),
            {
                "action": "generate_prompt",
                "job_description": "Python backend role.",
            },
        )
        payload = {
            "status": "success",
            "overall_match_score": 82,
            "match_level": "Strong",
            "ats_compatibility": {"score": 78, "status": "Good", "summary": "Clear backend match."},
            "summary": {
                "short_verdict": "Strong fit.",
                "candidate_positioning": "Backend engineer.",
                "recruiter_likely_impression": "Relevant experience.",
            },
            "strengths": [{"title": "Python", "evidence_from_resume": "Built APIs.", "relevance_to_job": "Core skill."}],
            "missing_keywords": [{"keyword": "Kubernetes", "importance": "Medium", "reason": "Not explicit."}],
            "matched_skills": [{"skill": "Django", "evidence_from_resume": "Built Django APIs."}],
            "gaps_or_risks": [{"gap": "Cloud", "why_it_matters": "Role mentions cloud.", "suggested_fix": "Add cloud work."}],
            "resume_improvement_suggestions": [
                {
                    "section": "Experience",
                    "current_issue": "Impact is described without numbers.",
                    "suggested_change": "Add quantified latency and reliability improvements.",
                    "reason": "Metrics make the backend impact easier to evaluate.",
                }
            ],
            "rewritten_bullets": [
                {
                    "original_bullet": "Built APIs.",
                    "improved_bullet": "Built Django APIs that reduced request latency by 35%.",
                    "why_better": "Adds measurable impact and keeps the technical context.",
                }
            ],
            "recommended_keywords_to_add_naturally": ["System Design", "Kubernetes"],
            "application_confidence": {"score": 80, "label": "High", "reason": "Good overlap."},
            "final_recommendation": "Apply with tailored keywords.",
        }

        response = self.client.post(
            reverse("product_dashboard"),
            {
                "action": "save_analysis_json",
                "analysis_json": json.dumps(payload),
            },
            follow=True,
        )

        analysis = ResumeAnalysis.objects.get(user=self.user)
        self.assertEqual(analysis.status, ResumeAnalysis.Status.RESULT_ADDED)
        self.assertEqual(analysis.ai_response_json["overall_match_score"], 82)
        self.assertContains(response, "Analysis Result")
        self.assertContains(response, "82%")
        self.assertContains(response, "Resume Improvement Suggestions")
        self.assertContains(response, "Add quantified latency and reliability improvements.")
        self.assertContains(response, "Rewritten Bullets")
        self.assertContains(response, "Built Django APIs that reduced request latency by 35%.")
        self.assertContains(response, "Recommended Keywords to Add Naturally")
        self.assertContains(response, "System Design")
        self.assertContains(response, "Apply with tailored keywords.")

    @override_settings(HACKERLEAP_AI_MODE="manual")
    def test_invalid_analysis_json_is_rejected(self):
        resume_file = SimpleUploadedFile("resume.pdf", b"%PDF-1.4\nresume\n%%EOF", content_type="application/pdf")
        with patch("apps.product.forms.extract_pdf_text", return_value="Python backend resume."):
            self.client.post(reverse("product_dashboard"), {"resume": resume_file})
        self.client.post(
            reverse("product_dashboard"),
            {
                "action": "generate_prompt",
                "job_description": "Python backend role.",
            },
        )

        response = self.client.post(
            reverse("product_dashboard"),
            {
                "action": "save_analysis_json",
                "analysis_json": "not-json",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please paste valid JSON.")

    @override_settings(HACKERLEAP_AI_MODE="manual")
    def test_analysis_json_missing_required_report_fields_is_rejected(self):
        resume_file = SimpleUploadedFile("resume.pdf", b"%PDF-1.4\nresume\n%%EOF", content_type="application/pdf")
        with patch("apps.product.forms.extract_pdf_text", return_value="Python backend resume."):
            self.client.post(reverse("product_dashboard"), {"resume": resume_file})
        self.client.post(
            reverse("product_dashboard"),
            {
                "action": "generate_prompt",
                "job_description": "Python backend role.",
            },
        )

        response = self.client.post(
            reverse("product_dashboard"),
            {
                "action": "save_analysis_json",
                "analysis_json": json.dumps({"status": "success"}),
            },
        )

        analysis = ResumeAnalysis.objects.get(user=self.user)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(analysis.status, ResumeAnalysis.Status.PROMPT_READY)
        self.assertContains(response, 'Analysis JSON must include &quot;overall_match_score&quot;.')

    @override_settings(HACKERLEAP_AI_MODE="manual")
    def test_analysis_json_over_server_limit_is_rejected(self):
        resume_file = SimpleUploadedFile("resume.pdf", b"%PDF-1.4\nresume\n%%EOF", content_type="application/pdf")
        with patch("apps.product.forms.extract_pdf_text", return_value="Python backend resume."):
            self.client.post(reverse("product_dashboard"), {"resume": resume_file})
        self.client.post(
            reverse("product_dashboard"),
            {
                "action": "generate_prompt",
                "job_description": "Python backend role.",
            },
        )

        response = self.client.post(
            reverse("product_dashboard"),
            {
                "action": "save_analysis_json",
                "analysis_json": "x" * 100001,
            },
        )

        analysis = ResumeAnalysis.objects.get(user=self.user)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(analysis.status, ResumeAnalysis.Status.PROMPT_READY)
        self.assertContains(response, "Please keep the analysis JSON under 100 KB.")

    def test_dashboard_recent_analysis_fetches_saved_results(self):
        analysis = self.create_analysis()

        response = self.client.get(reverse("product_dashboard"))

        self.assertContains(response, "Recent Analysis")
        self.assertContains(response, "Senior Backend Engineer")
        self.assertContains(response, "TechNova Inc.")
        self.assertContains(response, "82%")
        self.assertContains(response, reverse("analysis_detail", kwargs={"analysis_uuid": analysis.uuid}))
        self.assertNotContains(response, "Your resume match reports will appear here after you generate a prompt")

    def test_analysis_history_lists_user_analyses(self):
        analysis = self.create_analysis()

        response = self.client.get(reverse("analysis_history"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your resume match reports")
        self.assertContains(response, "Senior Backend Engineer")
        self.assertContains(response, reverse("analysis_detail", kwargs={"analysis_uuid": analysis.uuid}))

    def test_analysis_detail_displays_saved_result(self):
        analysis = self.create_analysis()

        response = self.client.get(reverse("analysis_detail", kwargs={"analysis_uuid": analysis.uuid}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Senior Backend Engineer")
        self.assertContains(response, "TechNova Inc.")
        self.assertContains(response, "Analysis Result")
        self.assertContains(response, "Resume Improvement Suggestions")
        self.assertContains(response, "Add quantified latency and reliability improvements.")
        self.assertContains(response, "Rewritten Bullets")
        self.assertContains(response, "Built Django APIs that reduced request latency by 35%.")
        self.assertContains(response, "Recommended Keywords to Add Naturally")
        self.assertContains(response, "System Design")
        self.assertContains(response, "Final Recommendation")
        self.assertContains(response, "Apply with tailored keywords.")

    def test_analysis_detail_displays_empty_states_for_missing_rewrite_sections(self):
        analysis = self.create_analysis(
            ai_response_json={
                "resume_improvement_suggestions": [],
                "rewritten_bullets": [],
                "recommended_keywords_to_add_naturally": [],
            }
        )

        response = self.client.get(reverse("analysis_detail", kwargs={"analysis_uuid": analysis.uuid}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No improvement suggestions returned.")
        self.assertContains(response, "No rewritten bullets returned.")
        self.assertContains(response, "No recommended keywords returned.")

    def test_analysis_detail_does_not_use_numeric_primary_key_url(self):
        analysis = self.create_analysis()

        response = self.client.get(f"/app/analysis/{analysis.id}/")

        self.assertEqual(response.status_code, 404)

    def test_user_cannot_view_another_users_analysis_detail(self):
        other_user = get_user_model().objects.create_user(
            username="other-analysis@example.com",
            email="other-analysis@example.com",
            password="Password1!",
        )
        analysis = self.create_analysis(user=other_user)

        response = self.client.get(reverse("analysis_detail", kwargs={"analysis_uuid": analysis.uuid}))

        self.assertEqual(response.status_code, 404)

    def test_staff_can_view_any_analysis_detail(self):
        other_user = get_user_model().objects.create_user(
            username="other-analysis@example.com",
            email="other-analysis@example.com",
            password="Password1!",
        )
        staff_user = get_user_model().objects.create_user(
            username="staff-analysis",
            email="staff-analysis@example.com",
            password="Password1!",
            is_staff=True,
        )
        analysis = self.create_analysis(user=other_user)
        self.client.force_login(staff_user)

        response = self.client.get(reverse("analysis_detail", kwargs={"analysis_uuid": analysis.uuid}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Senior Backend Engineer")

    def test_analysis_status_returns_progress_for_owner(self):
        analysis = self.create_analysis(
            status=ResumeAnalysis.Status.PROCESSING,
            ai_response_json=None,
            ai_provider="chatgpt",
        )

        response = self.client.get(reverse("analysis_status", kwargs={"analysis_uuid": analysis.uuid}))

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], ResumeAnalysis.Status.PROCESSING)
        self.assertEqual(data["display_status"], "Processing")
        self.assertFalse(data["is_complete"])
        self.assertFalse(data["is_failed"])
        self.assertGreaterEqual(data["progress"], 40)

    def test_user_cannot_poll_another_users_analysis_status(self):
        other_user = get_user_model().objects.create_user(
            username="other-status@example.com",
            email="other-status@example.com",
            password="Password1!",
        )
        analysis = self.create_analysis(user=other_user)

        response = self.client.get(reverse("analysis_status", kwargs={"analysis_uuid": analysis.uuid}))

        self.assertEqual(response.status_code, 404)

    def test_run_resume_analysis_task_saves_completed_result(self):
        analysis = self.create_analysis(
            status=ResumeAnalysis.Status.QUEUED,
            ai_response_json=None,
            generated_prompt="Queued prompt.",
            ai_provider="chatgpt",
        )
        ai_payload = {
            "status": "success",
            "role_title_detected": "Backend Engineer",
            "company_detected": "Acme",
            "overall_match_score": 88,
            "match_level": "Strong",
            "ats_compatibility": {"score": 86, "status": "Strong", "summary": "Good ATS fit."},
            "summary": {
                "short_verdict": "Strong fit.",
                "candidate_positioning": "Backend engineer.",
                "recruiter_likely_impression": "Relevant.",
            },
            "strengths": [],
            "missing_keywords": [],
            "matched_skills": [],
            "gaps_or_risks": [],
            "resume_improvement_suggestions": [],
            "rewritten_bullets": [],
            "recommended_keywords_to_add_naturally": [],
            "application_confidence": {"score": 84, "label": "High", "reason": "Good overlap."},
            "final_recommendation": "Apply.",
        }

        with patch(
            "apps.product.tasks.run_resume_match_analysis",
            return_value=ResumeMatchResult(
                generated_prompt="Completed prompt.",
                ai_response_json=ai_payload,
                provider="chatgpt",
            ),
        ) as ai_runner:
            run_resume_analysis(analysis.id)

        analysis.refresh_from_db()
        ai_runner.assert_called_once_with(
            job_description="Python backend role.",
            resume_text="Python Django resume.",
            mode="chatgpt",
        )
        self.assertEqual(analysis.status, ResumeAnalysis.Status.RESULT_ADDED)
        self.assertEqual(analysis.ai_response_json["overall_match_score"], 88)
        self.assertEqual(analysis.generated_prompt, "Completed prompt.")
        self.assertEqual(analysis.ai_provider, "chatgpt")
        self.assertIsNotNone(analysis.started_at)
        self.assertIsNotNone(analysis.completed_at)

    def test_run_resume_analysis_task_saves_failure(self):
        analysis = self.create_analysis(
            status=ResumeAnalysis.Status.QUEUED,
            ai_response_json=None,
            ai_provider="chatgpt",
        )

        with patch("apps.product.tasks.run_resume_match_analysis", side_effect=RuntimeError("Provider timed out")):
            run_resume_analysis(analysis.id)

        analysis.refresh_from_db()
        self.assertEqual(analysis.status, ResumeAnalysis.Status.FAILED)
        self.assertEqual(analysis.error_message, "Provider timed out")
        self.assertIsNotNone(analysis.completed_at)


class EarlyAccessSignupTests(TestCase):
    def test_invite_signup_creates_plain_user_and_logs_in(self):
        early_access_user = EarlyAccessUser.objects.create(email="invited@example.com", is_beta_active=False)

        response = self.client.post(
            reverse("early_access_signup", kwargs={"token": early_access_user.signup_token}),
            {
                "email": early_access_user.email,
                "date_of_birth": "1995-06-13",
                "password1": "StrongPass1!",
                "password2": "StrongPass1!",
            },
            follow=True,
        )

        user = get_user_model().objects.get(email="invited@example.com")
        early_access_user.refresh_from_db()
        self.assertEqual(early_access_user.date_of_birth.isoformat(), "1995-06-13")
        self.assertEqual(early_access_user.user, user)
        self.assertTrue(early_access_user.is_beta_active)
        self.assertIsNotNone(early_access_user.signup_completed_at)
        self.assertRedirects(response, reverse("product_dashboard"))

    def test_invite_signup_requires_strong_password(self):
        early_access_user = EarlyAccessUser.objects.create(email="invited@example.com", is_beta_active=False)

        response = self.client.post(
            reverse("early_access_signup", kwargs={"token": early_access_user.signup_token}),
            {
                "email": early_access_user.email,
                "date_of_birth": "1995-06-13",
                "password1": "weakpass",
                "password2": "weakpass",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(get_user_model().objects.filter(email="invited@example.com").exists())
        self.assertContains(response, "Password must include at least one uppercase letter.")

    def test_active_invite_does_not_render_signup(self):
        early_access_user = EarlyAccessUser.objects.create(email="invited@example.com", is_beta_active=True)

        response = self.client.get(reverse("early_access_signup", kwargs={"token": early_access_user.signup_token}))

        self.assertEqual(response.status_code, 404)

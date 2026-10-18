import copy
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.website.models import EarlyAccessUser
from .models import Resume, ResumeAnalysis, ResumeDraft, ResumeEditApplication
from .resume_builder import blank_content, render_resume
from .resume_edits import apply_edits, editable_targets, plan_token, review_edits, validate_edit_shape
from .services import build_resume_match_prompt, run_resume_match_analysis
from .tasks import run_resume_analysis


class ResumeEditsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('editor', password='test')
        EarlyAccessUser.objects.create(user=self.user, email='editor@example.test', is_beta_active=True)
        self.client.force_login(self.user)
        self.content = blank_content()
        self.content['contact']['name'] = 'Engineer'
        self.content['summary'] = 'Django engineer.'
        self.content['experience'] = [{'company': 'Acme', 'role': 'Engineer', 'context': '', 'dates': '2020', 'bullets': 'Built APIs.\r\nBuilt APIs.\r\n'}]
        self.draft = ResumeDraft.objects.create(user=self.user, title='Original', content=self.content)
        self.snapshot = {'draft_uuid': str(self.draft.uuid), 'revision': 1, 'template_version': 1, 'title': 'Original', 'content': copy.deepcopy(self.content)}
        self.resume = Resume.objects.create(user=self.user, original_filename='resume.pdf', size=1, parsed_text='Django engineer.', builder_snapshot=self.snapshot)
        self.edit = {'target_id': 'experience_0_bullet_1', 'original': 'Built APIs.', 'replacement': 'Developed APIs.', 'reason': 'Clearer phrasing.'}
        self.analysis = ResumeAnalysis.objects.create(user=self.user, resume=self.resume, job_description='Django role', resume_text='Django engineer.', builder_snapshot=self.snapshot, status=ResumeAnalysis.Status.RESULT_ADDED, ai_response_json={'status': 'success', 'resume_edits': [self.edit]})

    def url(self, action):
        return reverse('resume_edits_' + action, kwargs={'analysis_uuid': self.analysis.uuid})

    def submit(self, **changes):
        return self.client.post(self.url('apply'), {'plan_token': plan_token(self.analysis), 'targets': [self.edit['target_id']], **changes})

    def test_exact_scoped_replacement_preserves_unselected_text_and_line_endings(self):
        result = apply_edits(self.analysis, [self.edit['target_id']])
        expected = copy.deepcopy(self.content)
        expected['experience'][0]['bullets'] = 'Built APIs.\r\nDeveloped APIs.\r\n'
        self.assertEqual(result, expected)

    def test_reject_unknown_duplicate_mismatch_multiline_and_controls(self):
        for changes in [{'target_id': 'contact'}, {'original': 'Built  APIs.'}, {'replacement': 'one\ntwo'}, {'replacement': 'one\n'}, {'replacement': 'bad\x00'}]:
            self.analysis.ai_response_json['resume_edits'] = [{**self.edit, **changes}]
            self.assertTrue(review_edits(self.analysis)[0]['problem'])
            with self.assertRaises(ValidationError):
                apply_edits(self.analysis, [self.edit['target_id']])
        self.analysis.ai_response_json['resume_edits'] = [self.edit, self.edit]
        self.assertTrue(all(row['problem'] for row in review_edits(self.analysis)))
        for bad in [{}, [self.edit]*101, [{**self.edit, 'replacement': []}], [{**self.edit, 'extra': 'bad'}]]:
            with self.assertRaises(ValidationError):
                validate_edit_shape(bad)

    def test_review_escapes_ai_text_and_requires_selection(self):
        self.analysis.ai_response_json['resume_edits'][0]['replacement'] = '<script>alert(1)</script>'
        self.analysis.save()
        response = self.client.get(self.url('review'))
        self.assertContains(response, '&lt;script&gt;')
        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertEqual(self.submit(targets=[]).status_code, 400)
        self.assertEqual(self.submit(targets=['summary']).status_code, 400)
        self.assertIn('&lt;script&gt;', render_resume(apply_edits(self.analysis, [self.edit['target_id']])))

    def test_new_draft_uses_snapshot_and_retries_are_idempotent(self):
        self.draft.content = {**self.content, 'summary': 'Later changes.'}
        self.draft.revision = 2
        self.draft.save()
        first = self.submit()
        self.assertEqual(first.status_code, 302)
        second = self.submit()
        self.assertEqual(first.url, second.url)
        self.assertEqual(ResumeEditApplication.objects.count(), 1)
        generated = ResumeEditApplication.objects.get().draft
        self.assertEqual(generated.content['summary'], 'Django engineer.')
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.content['summary'], 'Later changes.')
        generated.delete()
        self.assertEqual(self.submit().status_code, 409)

    def test_stale_plan_no_snapshot_and_refusal_are_blocked(self):
        token = plan_token(self.analysis)
        self.analysis.ai_response_json['resume_edits'][0]['replacement'] = 'Changed suggestion.'
        self.analysis.save()
        self.assertEqual(self.submit(plan_token=token).status_code, 409)
        for changes in [{'builder_snapshot': {}}, {'ai_response_json': {'status': 'refused'}}, {'status': 'processing'}]:
            ResumeAnalysis.objects.filter(pk=self.analysis.pk).update(**changes)
            self.assertEqual(self.submit().status_code, 400)
        self.assertEqual(ResumeEditApplication.objects.count(), 0)

    def test_auth_ownership_csrf_and_methods(self):
        self.assertEqual(self.client.get(self.url('apply')).status_code, 405)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.user)
        self.assertEqual(csrf.post(self.url('apply')).status_code, 403)
        staff = get_user_model().objects.create_user('staff', is_staff=True)
        self.client.force_login(staff)
        self.assertEqual(self.client.get(self.url('review')).status_code, 404)
        self.assertEqual(self.submit().status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(self.url('review')).status_code, 302)

    def test_prompt_manual_and_worker_receive_exact_targets(self):
        targets = editable_targets(self.snapshot)
        self.assertEqual(targets[self.edit['target_id']], self.edit['original'])
        manual = run_resume_match_analysis(job_description='Django', resume_text='PDF text', mode='manual', builder_snapshot=self.snapshot)
        self.assertIn('experience_0_bullet_1', manual.generated_prompt)
        self.assertIn('"editable_targets": {}', build_resume_match_prompt('Django', 'PDF'))
        self.analysis.status = ResumeAnalysis.Status.QUEUED
        self.analysis.save()
        with patch('apps.product.tasks.run_resume_match_analysis', return_value=manual) as runner:
            run_resume_analysis(self.analysis.pk)
        self.assertEqual(runner.call_args.kwargs['builder_snapshot'], self.snapshot)

    @override_settings(HACKERLEAP_AI_MODE='manual')
    def test_dashboard_captures_snapshot_and_manual_result_is_bound_to_analysis(self):
        self.client.post(reverse('product_dashboard'), {'action': 'generate_prompt', 'job_description': 'Django developer'})
        created = ResumeAnalysis.objects.exclude(pk=self.analysis.pk).get()
        self.assertEqual(created.builder_snapshot, self.snapshot)
        self.assertIn('experience_0_bullet_1', created.generated_prompt)
        result = self.client.post(reverse('product_dashboard'), {'action': 'save_analysis_json', 'analysis_uuid': str(self.analysis.uuid), 'analysis_json': json.dumps({'status': 'refused', 'reason': 'No match'})})
        self.assertEqual(result.status_code, 302)
        self.analysis.refresh_from_db()
        created.refresh_from_db()
        self.assertEqual(self.analysis.result_data['status'], 'refused')
        self.assertIsNone(created.ai_response_json)

    def test_draft_limit(self):
        ResumeDraft.objects.bulk_create([ResumeDraft(user=self.user, content=self.content) for _ in range(19)])
        self.assertEqual(self.submit().status_code, 400)
        self.assertFalse(ResumeEditApplication.objects.exists())

    def test_automatic_provider_receives_structured_targets(self):
        from .services import ChatGPTResumeMatchClient
        with patch('openai.OpenAI') as sdk:
            sdk.return_value.chat.completions.create.return_value.choices[0].message.content = '{"status":"refused","reason":"No match"}'
            ChatGPTResumeMatchClient(api_key='test-key').analyze(job_description='Django', resume_text='PDF', builder_snapshot=self.snapshot)
            payload = json.loads(sdk.return_value.chat.completions.create.call_args.kwargs['messages'][1]['content'])
            self.assertEqual(payload['editable_targets'], editable_targets(self.snapshot))

    def test_pdf_upload_clears_builder_provenance(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from tempfile import TemporaryDirectory
        from .forms import ResumeUploadForm
        form = ResumeUploadForm()
        form.cleaned_data = {'resume': SimpleUploadedFile('external.pdf', b'%PDF-example', content_type='application/pdf')}
        form.parsed_text = 'External resume'
        with TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            resume = form.save(self.user)
        self.assertEqual(resume.builder_snapshot, {})
        self.analysis.refresh_from_db()
        self.assertEqual(self.analysis.builder_snapshot, self.snapshot)

    def test_improved_resume_exports_pdf(self):
        from io import BytesIO
        from pypdf import PdfReader
        from .resume_builder import render_pdf
        content = apply_edits(self.analysis, [self.edit['target_id']])
        pdf = render_pdf(content)
        text = ''.join(page.extract_text() for page in PdfReader(BytesIO(pdf)).pages)
        self.assertIn('Developed APIs.', text)
        self.assertIn('Built APIs.', text)

    def test_regenerate_button_visible_above_and_below_results(self):
        for url in (reverse('product_dashboard'), reverse('analysis_detail', kwargs={'analysis_uuid': self.analysis.uuid})):
            response = self.client.get(url)
            self.assertContains(response, 'Regenerate resume', count=2)
            self.assertContains(response, 'class="outline-action" href="' + self.url('review') + '"', count=2)
            html = response.content.decode()
            self.assertLess(html.index('Regenerate resume'), html.index('Final Recommendation'))
            self.assertGreater(html.rindex('Regenerate resume'), html.index('Final Recommendation'))
        self.analysis.builder_snapshot = {}
        self.analysis.save()
        response = self.client.get(reverse('analysis_detail', kwargs={'analysis_uuid': self.analysis.uuid}))
        self.assertNotContains(response, 'Regenerate resume')
        self.assertContains(response, 'Choose a builder resume')

    def prepare_keywords(self):
        self.analysis.builder_snapshot['content']['skills'] = [{'label': 'Backend', 'items': 'Python, Django'}]
        self.analysis.ai_response_json['recommended_keywords_to_add_naturally'] = [' python ', 'Redis', 'REDIS', 'PostgreSQL']
        self.analysis.save()

    def test_recommended_skills_review_and_keyword_only_regeneration(self):
        self.prepare_keywords()
        response = self.client.get(self.url('review'))
        self.assertContains(response, 'already in Skills')
        self.assertContains(response, 'name="skills" value="1"')
        self.assertNotContains(response, 'name="skills" value="2"')
        self.assertNotContains(response, 'checked')
        first = self.submit(targets=[], skills=['1', '3'], skill_group='0', confirm_skills='1')
        self.assertEqual(first.status_code, 302)
        second = self.submit(targets=[], skills=['3', '1'], skill_group='0', confirm_skills='1')
        self.assertEqual(first.url, second.url)
        draft = ResumeEditApplication.objects.get().draft
        self.assertEqual(draft.content['skills'][0]['items'], 'Python, Django, Redis, PostgreSQL')
        self.assertEqual(draft.content['experience'], self.content['experience'])
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.content, self.content)

    def test_keywords_require_confirmation_valid_selection_and_group(self):
        self.prepare_keywords()
        for changes in [{'confirm_skills': ''}, {'skills': ['0']}, {'skills': ['2']}, {'skills': ['999']}, {'skills': ['1', '1']}, {'skill_group': '-1'}]:
            data = {'targets': [], 'skills': ['1'], 'skill_group': '0', 'confirm_skills': '1', **changes}
            self.assertEqual(self.submit(**data).status_code, 400)
        self.assertFalse(ResumeEditApplication.objects.exists())

    def test_combined_edits_new_group_and_stale_keyword_plan(self):
        self.prepare_keywords()
        token = plan_token(self.analysis)
        self.analysis.ai_response_json['recommended_keywords_to_add_naturally'].append('Docker')
        self.analysis.save()
        self.assertEqual(self.submit(plan_token=token, skills=['1'], skill_group='new', confirm_skills='1').status_code, 409)
        self.assertEqual(self.submit(skills=['1'], skill_group='new', confirm_skills='1').status_code, 302)
        draft = ResumeEditApplication.objects.get().draft
        self.assertEqual(draft.content['skills'][-1], {'label': 'Additional skills', 'items': 'Redis'})
        self.assertIn('Developed APIs.', draft.content['experience'][0]['bullets'])

    def test_keyword_additions_obey_content_limits(self):
        self.prepare_keywords()
        self.analysis.builder_snapshot['content']['skills'] = [{'label': 'Group', 'items': 'x' * 1200} for _ in range(12)]
        self.analysis.save()
        for group in ['0', 'new']:
            self.assertEqual(self.submit(targets=[], skills=['1'], skill_group=group, confirm_skills='1').status_code, 400)

    def test_regeneration_preserves_typography(self):
        typography = {'font': 'georgia', 'body_size': 11, 'heading_size': 13, 'name_size': 24}
        self.analysis.builder_snapshot['content']['typography'] = typography
        self.analysis.save()
        self.assertEqual(self.submit().status_code, 302)
        self.assertEqual(ResumeEditApplication.objects.get().draft.content['typography'], typography)

import copy
import json
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, Client, override_settings
from django.urls import reverse

from apps.website.models import EarlyAccessUser
from .models import InterviewSimulatorSession, MockInterviewSession, MockInterviewTurn, ResumeDraft, Resume
from .resume_builder import blank_content
from .interview_simulator import build_prompt, runtime_prompt, interview_context
from .services import create_mock_interview_realtime_token, generate_mock_interview_feedback, get_user_feature_flags


class SimulatorTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('simulator', password='test')
        EarlyAccessUser.objects.create(user=self.user, email='simulator@example.test', is_beta_active=True)
        self.client.force_login(self.user)
        content = blank_content()
        content['contact']['name'] = 'Candidate'
        content['summary'] = 'Built reliable Python services.'
        self.draft = ResumeDraft.objects.create(user=self.user, title='Backend resume', content=content)
        self.data = {'company':'Example', 'round_type':'behavioural', 'role':'Backend Engineer',
            'briefing':'Discuss collaboration and conflict.', 'job_description':'Build and operate Python APIs.',
            'resume_choice':f'draft:{self.draft.uuid}', 'match_experience':'on', 'match_values':'on', 'values':'Customer focus'}

    def create_session(self):
        response = self.client.post(reverse('simulator_setup'), self.data)
        self.assertEqual(response.status_code, 302)
        return InterviewSimulatorSession.objects.latest('created_at')

    def url(self, action, session):
        return reverse('simulator_' + action, kwargs={'session_uuid':session.uuid})

    def test_create_snapshot_and_separate_history_and_routes(self):
        session = self.create_session()
        system = MockInterviewSession.objects.create(user=self.user, topic='System-only topic')
        self.assertEqual(session.resume_snapshot['content'], self.draft.content)
        self.assertIn('Customer focus', session.prompt_snapshot)
        self.assertContains(self.client.get(reverse('simulator_history')), session.topic)
        self.assertNotContains(self.client.get(reverse('simulator_history')), system.topic)
        self.assertNotContains(self.client.get(reverse('mock_interview_history')), session.topic)
        self.assertEqual(self.client.get(reverse('mock_interview_room', kwargs={'session_uuid':session.uuid})).status_code, 404)
        self.assertEqual(self.client.get(self.url('room', system)).status_code, 404)
        room = self.client.get(self.url('room', session))
        self.assertContains(room, self.url('token', session))
        self.assertContains(room, 'data-simulator="true"')
        self.assertIn('no-store', room['Cache-Control'])

    def test_reuse_retains_exact_prompt_after_resume_deleted_and_discards_conversation(self):
        session = self.create_session()
        session.prompt_snapshot = 'Original immutable prompt version'
        session.transcript_text = 'OLD ANSWER'
        session.feedback_json = {'summary':'OLD FEEDBACK'}
        session.save()
        MockInterviewTurn.objects.create(session=session, role='user', text='OLD ANSWER')
        self.draft.delete()
        reuse = reverse('simulator_reuse', kwargs={'source_uuid':session.uuid})
        self.assertContains(self.client.get(reuse), 'Reuse saved resume: Backend resume')
        data = dict(self.data, resume_choice='snapshot')
        self.assertEqual(self.client.post(reuse, data).status_code, 302)
        fresh = InterviewSimulatorSession.objects.latest('created_at')
        self.assertNotEqual(fresh.pk, session.pk)
        self.assertEqual(fresh.prompt_snapshot, session.prompt_snapshot)
        self.assertEqual(fresh.resume_text, session.resume_text)
        self.assertEqual(fresh.transcript_text, '')
        self.assertFalse(fresh.turns.exists())
        self.assertIsNone(fresh.feedback_json)
        self.assertIsNone(fresh.started_at)

    def test_edit_reuse_rebuilds_prompt_without_old_answers(self):
        session = self.create_session()
        response = self.client.post(reverse('simulator_reuse', kwargs={'source_uuid':session.uuid}), dict(self.data, company='New company', resume_choice='snapshot'))
        self.assertEqual(response.status_code,302)
        fresh = InterviewSimulatorSession.objects.latest('created_at')
        self.assertIn('New company', fresh.prompt_snapshot)
        session.refresh_from_db()
        self.assertEqual(session.setup['company'], 'Example')

    def test_validation(self):
        for change in [{'round_type':'other'}, {'values':''}, {'match_vision':'on'}, {'match_mission':'on'},
                       {'company':'x'*201}, {'job_description':'x'*12001}, {'resume_choice':'draft:invalid'}]:
            with self.subTest(change=change):
                self.assertEqual(self.client.post(reverse('simulator_setup'), dict(self.data, **change)).status_code,400)
        self.assertFalse(InterviewSimulatorSession.objects.exists())

    def test_private_resumes_sessions_and_csrf(self):
        session = self.create_session()
        other = get_user_model().objects.create_user('other', password='test', is_staff=True)
        self.client.force_login(other)
        self.assertNotContains(self.client.get(reverse('simulator_setup')), 'Backend resume')
        self.assertEqual(self.client.post(reverse('simulator_setup'), self.data).status_code,400)
        for action in ['room','feedback','token','turns','finish']:
            method = self.client.get if action in ['room','feedback'] else self.client.post
            self.assertEqual(method(self.url(action,session)).status_code,404)
        self.assertEqual(self.client.get(reverse('simulator_reuse',kwargs={'source_uuid':session.uuid})).status_code,404)
        client=Client(enforce_csrf_checks=True);client.force_login(self.user)
        self.assertEqual(client.post(reverse('simulator_setup'),self.data).status_code,403)
        client.logout()
        self.assertEqual(client.get(reverse('simulator_history')).status_code,302)

    def test_uploaded_resume_snapshot(self):
        resume=Resume.objects.create(user=self.user, original_filename='resume.pdf', size=100, parsed_text='Candidate built Python APIs.')
        self.data['resume_choice']=f'uploaded:{resume.uuid}'
        session=self.create_session();resume.delete()
        self.assertEqual(session.resume_text,'Candidate built Python APIs.')

    def test_disabled_company_criteria_excluded_from_prompt(self):
        session=self.create_session()
        data=dict(session.setup, match_values=False, values='Do not send disabled values')
        prompt=build_prompt(data,session.resume_text)
        self.assertNotIn('Do not send disabled values',prompt)
        self.assertIn('untrusted reference data',prompt)
        self.assertIn('Continue from',runtime_prompt(session,'Candidate: My example'))

    @override_settings(OPENAI_API_KEY='test')
    def test_realtime_and_feedback_use_simulator_context(self):
        session=self.create_session()
        response=MagicMock();response.__enter__.return_value.read.return_value=b'{"value":"token"}'
        with patch('apps.product.services.urllib.request.urlopen', return_value=response) as call:
            create_mock_interview_realtime_token(self.user,session)
        payload=json.loads(call.call_args.args[0].data)
        self.assertEqual(payload['session']['instructions'],session.prompt_snapshot)
        feedback={'overall_score':70,'summary':'Evidence-based review','strengths':[],'gaps':[], 'missed_topics':[], 'better_answer_outline':[], 'next_practice_steps':[]}
        with patch('openai.OpenAI') as api:
            api.return_value.chat.completions.create.return_value.choices[0].message.content=json.dumps(feedback)
            generate_mock_interview_feedback(session)
        messages=api.return_value.chat.completions.create.call_args.kwargs['messages']
        self.assertIn('role/round', messages[0]['content'])
        context=json.loads(messages[1]['content'])
        self.assertEqual(context['setup'],interview_context(session.setup,session.resume_text))
        self.assertNotIn('level',context)

    def test_voice_lifecycle_quota_retry_and_feedback_destination(self):
        session=self.create_session()
        with patch('apps.product.views.create_mock_interview_realtime_token', side_effect=ValidationError('Unavailable')):
            self.assertEqual(self.client.post(self.url('token',session)).status_code,400)
        with patch('apps.product.views.create_mock_interview_realtime_token', return_value={'value':'token'}):
            self.assertEqual(self.client.post(self.url('token',session)).status_code,200)
            self.assertEqual(self.client.post(self.url('token',session)).status_code,200)
        session.refresh_from_db()
        self.assertEqual(session.status,'active')
        self.assertEqual(get_user_feature_flags(self.user).mock_interview_count,1)
        turn=self.client.post(self.url('turns',session),{'role':'user','text':'I resolved a customer incident.'},content_type='application/json')
        self.assertEqual(turn.status_code,200)
        with patch('apps.product.views.generate_mock_interview_feedback',return_value={'overall_score':80,'summary':'Good examples'}):
            response=self.client.post(self.url('finish',session))
        self.assertEqual(response.json()['feedback_url'],self.url('feedback',session))
        self.assertContains(self.client.get(self.url('feedback',session)), 'Start another interview')
        self.assertEqual(self.client.post(self.url('token',session)).status_code,400)
        fresh=self.create_session()
        with patch('apps.product.views.create_mock_interview_realtime_token') as token:
            self.assertEqual(self.client.post(self.url('token',fresh)).status_code,429)
            token.assert_not_called()

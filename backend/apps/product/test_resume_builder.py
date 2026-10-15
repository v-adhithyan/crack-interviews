import copy
import json
import subprocess
from io import BytesIO
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from pypdf import PdfReader, PdfWriter

from apps.website.models import EarlyAccessUser
from .models import Resume, ResumeDraft
from .resume_builder import blank_content, render_resume, render_pdf
from .resume_pdf_worker import deny_resource


class ResumeBuilderTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user('writer', password='test-password')
        EarlyAccessUser.objects.create(user=self.user, email='writer@example.test', is_beta_active=True)
        self.other = get_user_model().objects.create_user('other', is_staff=True)
        self.client.force_login(self.user)
        self.content = blank_content()
        self.content['contact']['name'] = 'Sample Engineer'
        self.draft = ResumeDraft.objects.create(user=self.user, title='My resume', content=self.content)

    def url(self, action, draft=None):
        return reverse('resume_builder_' + action, kwargs={'draft_uuid': (draft or self.draft).uuid})

    def save(self, **changes):
        return self.client.post(self.url('save'), {'title': 'Updated', 'content': self.content, 'revision': 1, **changes}, content_type='application/json')

    def test_atomic_revision_conflict_preserves_first_save(self):
        self.assertEqual(self.save().json()['revision'], 2)
        response = self.save(title='Stale overwrite')
        self.assertEqual(response.status_code, 409)
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.title, 'Updated')
        self.assertEqual(self.draft.revision, 2)
        self.assertEqual(self.save(revision=2, title='New version').json()['revision'], 3)

    def test_owner_only_even_for_staff(self):
        private = ResumeDraft.objects.create(user=self.other, content=self.content)
        for action in ['edit', 'save', 'preview', 'export', 'use', 'delete']:
            response = self.client.get(self.url(action, private)) if action == 'edit' else self.client.post(self.url(action, private), {})
            self.assertEqual(response.status_code, 404, action)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.url('edit')).status_code, 404)
        self.assertNotContains(self.client.get(reverse('resume_builder_list')), 'My resume')

    def test_auth_csrf_and_methods(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        self.assertEqual(csrf_client.post(self.url('save'), {}, content_type='application/json').status_code, 403)
        for action in ['save','preview','export','use','delete']:
            self.assertEqual(self.client.get(self.url(action)).status_code, 405)
        self.client.logout()
        self.assertEqual(self.client.get(self.url('edit')).status_code, 302)

    def test_validation_rejects_bad_shapes_and_bounds(self):
        for change in [{'revision': True}, {'revision': -1}, {'title': 'x'*121}, {'content': {}}, {'owner': self.other.pk}]:
            self.assertEqual(self.save(**change).status_code, 400)
        for content in [{**self.content,'skills':[{}]}, {**self.content,'summary':['wrong']}, {**self.content,'education':[{}]*11}]:
            self.assertEqual(self.save(content=content).status_code,400)
        for raw in [' ' * 100001, '{"a":1,"a":2}', '['*2000, '\xff']:
            self.assertEqual(self.client.post(self.url('save'),raw,content_type='application/json').status_code,400)
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.revision,1)

    def test_preview_escaped_and_not_persisted(self):
        content=copy.deepcopy(self.content)
        content['contact']['name']='</script><img src="file:///etc/passwd">'
        content['experience']=[{'company':'Example','role':'Engineer','context':'Remote','dates':'2020 - Present','bullets':'**Improved performance** <script>alert(1)</script>'}]
        response=self.client.post(self.url('preview'),{'content':content},content_type='application/json')
        self.assertEqual(response.status_code,200)
        html=response.json()['html']
        self.assertNotIn('<script>alert',html)
        self.assertNotIn('<img src=',html)
        self.assertIn('<strong>Improved performance</strong>',html)
        self.assertIn('&lt;script&gt;',html)
        self.assertEqual(response['Cache-Control'].split(',')[0], 'max-age=0')
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.content,self.content)

    def test_create_list_delete_and_quota(self):
        response=self.client.post(reverse('resume_builder_create'))
        self.assertEqual(response.status_code,302)
        self.assertEqual(ResumeDraft.objects.filter(user=self.user).count(),2)
        ResumeDraft.objects.bulk_create([ResumeDraft(user=self.user,content=self.content) for _ in range(18)])
        self.client.post(reverse('resume_builder_create'))
        self.assertEqual(ResumeDraft.objects.filter(user=self.user).count(),20)
        self.assertEqual(self.client.post(self.url('delete'),{'revision':2}).status_code,409)
        self.assertEqual(self.client.post(self.url('delete'),{'revision':1}).status_code,302)
        self.assertFalse(ResumeDraft.objects.filter(pk=self.draft.pk).exists())

    @patch('apps.product.resume_builder_views.render_pdf', return_value=b'%PDF-fake')
    def test_export_saved_version_headers_and_throttle(self, renderer):
        response=self.client.post(self.url('export'),{'revision':1,'download':'1'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response['Content-Type'],'application/pdf')
        self.assertIn('attachment',response['Content-Disposition'])
        renderer.assert_called_once_with(self.content)
        self.assertEqual(self.client.post(self.url('export'),{'revision':1}).status_code,429)
        self.assertEqual(self.client.post(self.url('export'),{'revision':2}).status_code,409)
        self.assertFalse(Resume.objects.filter(user=self.user).exists())

    @patch('apps.product.resume_builder_views.render_pdf', side_effect=RuntimeError('Unavailable'))
    def test_export_failure_keeps_draft(self, renderer):
        self.assertEqual(self.client.post(self.url('export'),{'revision':1}).status_code,503)
        self.assertTrue(ResumeDraft.objects.filter(pk=self.draft.pk).exists())

    def test_renderer_blocks_resources_and_timeout(self):
        for url in ['https://example.com', 'file:///etc/passwd', 'data:text/html,hello']:
            with self.assertRaises(ValueError):deny_resource(url)
        with patch('apps.product.resume_builder.subprocess.run', side_effect=subprocess.TimeoutExpired('worker',20)):
            with self.assertRaises(RuntimeError):render_pdf(self.content)

    def test_explicit_use_for_analysis(self):
        buffer=BytesIO(); writer=PdfWriter(); writer.add_blank_page(width=595,height=842); writer.write(buffer)
        with TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory), patch('apps.product.resume_builder_views.render_pdf',return_value=buffer.getvalue()):
            response=self.client.post(self.url('use'),{'revision':1})
            self.assertEqual(response.status_code,302)
            resume=Resume.objects.get(user=self.user)
            self.assertEqual(resume.content_type,'application/pdf')
            self.assertEqual(resume.size,len(buffer.getvalue()))
            self.assertEqual(len(PdfReader(resume.file).pages),1)

    def test_editor_uses_safe_json_and_sandboxed_preview(self):
        self.draft.title='</script><script>alert(1)</script>'
        self.draft.save()
        response=self.client.get(self.url('edit'))
        self.assertEqual(response.status_code,200)
        self.assertNotContains(response,'</script><script>alert')
        self.assertContains(response,'sandbox=""')
        self.assertContains(response,'resume-initial')

    def test_use_rechecks_revision_after_pdf_generation(self):
        buffer=BytesIO(); writer=PdfWriter(); writer.add_blank_page(width=595,height=842); writer.write(buffer)
        def changed_during_render(content):
            ResumeDraft.objects.filter(pk=self.draft.pk).update(revision=2)
            return buffer.getvalue()
        with patch('apps.product.resume_builder_views.render_pdf',side_effect=changed_during_render):
            self.assertEqual(self.client.post(self.url('use'),{'revision':1}).status_code,409)
        self.assertFalse(Resume.objects.filter(user=self.user).exists())

    def test_blank_name_export_is_validation_error(self):
        self.draft.content=blank_content(); self.draft.save()
        response=self.client.post(self.url('export'),{'revision':1})
        self.assertEqual(response.status_code,400)
        self.assertIn('full name',response.content.decode())

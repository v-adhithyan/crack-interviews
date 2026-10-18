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
        for action in ['edit', 'save', 'preview', 'export', 'use', 'delete', 'clone']:
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
            self.assertEqual(resume.builder_snapshot['draft_uuid'], str(self.draft.uuid))
            self.assertEqual(resume.builder_snapshot['content'], self.content)
            self.assertEqual(resume.builder_snapshot['revision'], 1)
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

    def test_pdf_uses_virtualenv_python_under_uwsgi(self):
        import sys
        from pathlib import Path
        with patch('apps.product.resume_builder.sys.executable', '/usr/local/bin/uwsgi'), patch('apps.product.resume_builder.subprocess.run') as runner:
            runner.return_value.stdout = b'%PDF-test'
            self.assertEqual(render_pdf(self.content), b'%PDF-test')
        self.assertEqual(runner.call_args.args[0][0], str(Path(sys.prefix) / 'bin/python'))

    def test_pdf_interpreter_override_and_missing_interpreter(self):
        from .resume_builder import pdf_python_executable
        import sys
        from pathlib import Path
        interpreter = str(Path(sys.prefix) / 'bin/python')
        with override_settings(RESUME_PDF_PYTHON=interpreter):
            self.assertEqual(pdf_python_executable(), interpreter)
        with override_settings(RESUME_PDF_PYTHON='/missing/venv/bin/python'), self.assertLogs('apps.product.resume_builder', level='ERROR') as logs:
            with self.assertRaises(RuntimeError):
                render_pdf(self.content)
        self.assertIn('Traceback', logs.output[0])

    def test_clone_copies_saved_content_without_changing_source(self):
        self.draft.revision = 4
        self.draft.save()
        response = self.client.post(self.url('clone'))
        self.assertRedirects(response, reverse('resume_builder_list'))
        clone = ResumeDraft.objects.exclude(pk=self.draft.pk).get()
        self.assertNotEqual(clone.uuid, self.draft.uuid)
        self.assertEqual(clone.user, self.user)
        self.assertEqual(clone.title, 'My resume (clone)')
        self.assertEqual(clone.template_version, self.draft.template_version)
        self.assertEqual(clone.content, self.draft.content)
        self.assertEqual(clone.revision, 1)
        clone.content['summary'] = 'Changed clone'
        clone.save()
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.content, self.content)
        self.assertEqual(self.draft.title, 'My resume')
        self.assertEqual(self.draft.revision, 4)

    def test_clone_requires_post_csrf_and_authentication(self):
        for method in ('get', 'head', 'put', 'delete'):
            self.assertEqual(getattr(self.client, method)(self.url('clone')).status_code, 405)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        self.assertEqual(csrf_client.post(self.url('clone')).status_code, 403)
        page = csrf_client.get(reverse('resume_builder_list'))
        self.assertContains(page, 'method="post" action="' + self.url('clone') + '"')
        token = csrf_client.cookies['csrftoken'].value
        self.assertEqual(csrf_client.post(self.url('clone'), {'csrfmiddlewaretoken': token}).status_code, 302)
        self.client.logout()
        self.assertEqual(self.client.post(self.url('clone')).status_code, 302)
        self.assertEqual(ResumeDraft.objects.count(), 2)

    def test_clone_staff_cannot_copy_another_users_draft(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.url('clone')).status_code, 404)
        self.assertEqual(ResumeDraft.objects.count(), 1)

    def test_clone_respects_draft_limit_and_title_length(self):
        self.draft.title = 'x' * 120
        self.draft.save()
        self.client.post(self.url('clone'))
        clone = ResumeDraft.objects.exclude(pk=self.draft.pk).get()
        self.assertEqual(len(clone.title), 120)
        self.assertTrue(clone.title.endswith(' (clone)'))
        ResumeDraft.objects.bulk_create([ResumeDraft(user=self.user, content=self.content) for _ in range(18)])
        response = self.client.post(self.url('clone'), follow=True)
        self.assertContains(response, 'You can keep up to 20 resume drafts')
        self.assertEqual(ResumeDraft.objects.count(), 20)

    def test_typography_defaults_and_legacy_drafts(self):
        from .resume_builder import DEFAULT_TYPOGRAPHY, validate_content
        self.assertEqual(self.content['typography'], DEFAULT_TYPOGRAPHY)
        legacy = {key: value for key, value in self.content.items() if key != 'typography'}
        self.assertEqual(validate_content(legacy), legacy)
        html = render_resume(legacy)
        self.assertIn('font-size:10.5pt', html)
        self.assertIn('font-size:22pt', html)
        self.assertIn('font-size:12pt', html)
        self.assertIn('class="font-default"', html)

    def test_typography_saves_previews_and_clones(self):
        self.content['typography'] = {'font': 'garamond', 'body_size': 11.5, 'heading_size': 14, 'name_size': 26}
        self.assertEqual(self.save().status_code, 200)
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.content['typography'], self.content['typography'])
        html = render_resume(self.draft.content)
        self.assertIn('class="font-garamond"', html)
        for size in ['11.5', '14', '26']:
            self.assertIn(f'font-size:{size}pt', html)
        self.client.post(self.url('clone'))
        self.assertEqual(ResumeDraft.objects.exclude(pk=self.draft.pk).get().content['typography'], self.content['typography'])
        response = self.client.get(self.url('edit'))
        self.assertContains(response, 'typography_defaults')
        for name in ['Calibri', 'Arial', 'Helvetica', 'Garamond', 'Cambria', 'Georgia']:
            self.assertContains(response, name)

    def test_typography_rejects_css_injection_invalid_sizes_and_types(self):
        from .resume_builder import validate_content
        from django.core.exceptions import ValidationError
        for changes in [{'font': 'Arial; background:url(https://example.com)'}, {'font': []}, {'body_size': True}, {'body_size': '11'}, {'body_size': 100}, {'name_size': 12}, {'heading_size': float('nan')}, {'extra': 'value'}]:
            content = copy.deepcopy(self.content)
            content['typography'].update(changes)
            with self.assertRaises(ValidationError):
                validate_content(content)
        with self.assertRaises(ValidationError):
            validate_content({**self.content, 'typography': {}})

    def test_all_font_choices_generate_readable_pdfs(self):
        from .resume_builder import FONT_CHOICES
        for font in FONT_CHOICES:
            with self.subTest(font=font):
                content = copy.deepcopy(self.content)
                content['typography']['font'] = font
                pdf = render_pdf(content)
                self.assertIn('Sample Engineer', PdfReader(BytesIO(pdf)).pages[0].extract_text())

    def test_bundled_fonts_only_allow_registered_resources(self):
        from .resume_fonts import FONT_FILES
        for name in FONT_FILES:
            resource = deny_resource('resume-font:' + name)
            self.assertEqual(resource.info().get_content_type(), 'font/ttf')
            self.assertTrue(resource.read())
            resource.close()
        for url in ['resume-font:../secret.ttf', 'resume-font:%2e%2e/secret.ttf', 'resume-font:LiberationSans-Regular.ttf?x=1', 'resume-font:missing.ttf', 'file:///etc/passwd', 'https://example.com/font.ttf']:
            with self.assertRaises(ValueError):
                deny_resource(url)

    def test_browser_and_pdf_use_same_bundled_font_faces(self):
        html = render_resume(self.content)
        self.assertIn('/static/product/fonts/LiberationSans-Regular.ttf', html)
        self.assertIn('@font-face', html)
        pdf_html = render_resume(self.content, for_pdf=True)
        self.assertIn('resume-font:LiberationSans-Regular.ttf', pdf_html)
        self.assertNotIn('/static/', pdf_html)
        pdf = render_pdf(self.content)
        fonts = PdfReader(BytesIO(pdf)).pages[0]['/Resources']['/Font']
        from fontTools.ttLib import TTFont
        for value in fonts.values():
            descriptor = value.get_object()['/DescendantFonts'][0].get_object()['/FontDescriptor']
            embedded = TTFont(BytesIO(descriptor['/FontFile2'].get_data()))
            self.assertIn('Liberation Sans', embedded['name'].getDebugName(1))

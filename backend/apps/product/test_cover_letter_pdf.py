from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.template.loader import render_to_string
from pypdf import PdfReader

from .models import ResumeAnalysis, AnalysisFollowup
from .resume_builder import render_document_pdf
from .resume_fonts import FAMILIES, faces


class CoverLetterPdfTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user('adhi', is_staff=True)
        self.client.force_login(self.user)
        analysis = ResumeAnalysis.objects.create(user=self.user, job_description='Job', resume_text='Resume',
            generated_prompt='', ai_response_json={'company_detected': 'Example Company'})
        self.job = AnalysisFollowup.objects.create(analysis=analysis, request_key='test', questions=['Why?'],
            prompt='', status='ready', include_cover_letter=True, result={'cover_letter': 'Dear hiring team,\n\nI build Python services.\n\nRegards,\nAdhi'})
        self.url = reverse('analysis_followup_cover_letter_pdf', args=[self.job.uuid])

    @patch('apps.product.followup_views.render_document_pdf', return_value=b'%PDF-test')
    def test_download_filename_privacy_and_rate_limit(self, renderer):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertEqual(response['Content-Disposition'], 'attachment; filename="adhi_example-company_cover_letter.pdf"')
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(b''.join(response.streaming_content), b'%PDF-test')
        self.assertContains(self.client.get(reverse('analysis_followup_detail', args=[self.job.uuid])), 'Download PDF')
        self.assertEqual(self.client.get(self.url).status_code, 429)
        renderer.assert_called_once()

    @patch('apps.product.followup_views.render_document_pdf')
    def test_owner_only_and_completed_letter_required(self, renderer):
        other = get_user_model().objects.create_user('other', is_staff=True)
        self.client.force_login(other)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.client.force_login(self.user)
        for changes in [{'status':'processing'}, {'include_cover_letter':False}, {'result':{'cover_letter':''}}]:
            AnalysisFollowup.objects.filter(pk=self.job.pk).update(status='ready', include_cover_letter=True, result={'cover_letter':'Letter'})
            AnalysisFollowup.objects.filter(pk=self.job.pk).update(**changes)
            self.assertEqual(self.client.get(self.url).status_code, 404)
        renderer.assert_not_called()
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)

    @patch('apps.product.followup_views.render_document_pdf', side_effect=RuntimeError('private diagnostic'))
    def test_render_error_is_safe(self, renderer):
        response=self.client.get(self.url)
        self.assertEqual(response.status_code, 503)
        self.assertNotContains(response, 'private diagnostic', status_code=503)

    def test_real_pdf_preserves_text_and_escapes_html(self):
        letter='Dear hiring team,\n\nI build Python services.\n<script>not executable</script>\n\nRegards,\nAdhi'
        html=render_to_string('product/cover_letter_pdf.html', {'letter':letter, 'font_faces':[
            {'url':'resume-font:'+name,'style':style,'weight':weight} for name,style,weight in faces(FAMILIES['default'])]})
        self.assertNotIn('<script>', html)
        pdf=render_document_pdf(html)
        reader=PdfReader(BytesIO(pdf))
        self.assertEqual(len(reader.pages), 1)
        text=reader.pages[0].extract_text()
        self.assertIn('I build Python services.', text)
        self.assertIn('<script>not executable</script>', text)

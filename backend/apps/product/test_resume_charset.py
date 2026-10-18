from importlib import import_module
from unittest import skipUnless

from django.apps import apps
from django.db import connection, DatabaseError
from django.test import TransactionTestCase

upgrade_resume_text = import_module('apps.product.migrations.0019_resume_text_utf8mb4').upgrade_resume_text


@skipUnless(connection.vendor == 'mysql', 'Regression requires MySQL character sets')
class ResumeCharsetTests(TransactionTestCase):
    def test_legacy_columns_upgrade_and_round_trip_four_byte_unicode(self):
        from django.contrib.auth import get_user_model
        from .models import Resume, ResumeAnalysis, ResumeDraft

        # The test database contains no resume data yet. Simulate an old deployment.
        with connection.cursor() as cursor:
            for model in (Resume, ResumeAnalysis, ResumeDraft):
                cursor.execute(
                    f'ALTER TABLE {connection.ops.quote_name(model._meta.db_table)} '
                    'CONVERT TO CHARACTER SET utf8mb3 COLLATE utf8mb3_general_ci'
                )
        user = get_user_model().objects.create_user('unicode-regression')
        resume = Resume.objects.create(user=user, original_filename='resume.pdf', size=1, parsed_text='தமிழ் • Engineer')
        with self.assertRaises(DatabaseError) as failure:
            ResumeAnalysis.objects.create(user=user, resume=resume, job_description='💰 Compensation')
        self.assertEqual(failure.exception.args[0], 1366)
        with connection.schema_editor() as editor:
            upgrade_resume_text(apps, editor)
            upgrade_resume_text(apps, editor)  # A partially completed migration is retryable.

        resume.refresh_from_db()
        self.assertEqual(resume.parsed_text, 'தமிழ் • Engineer')
        text = '💰 Compensation • Engineer 🚀 தமிழ்'
        resume.original_filename = 'Resume 🚀.pdf'
        resume.parsed_text = text
        resume.save()
        analysis = ResumeAnalysis.objects.create(user=user, resume=resume, job_description=text, resume_text=text, generated_prompt=text)
        draft = ResumeDraft.objects.create(user=user, title='Resume 🚀', content={'summary': text})
        for instance in (resume, analysis, draft):
            instance.refresh_from_db()
        self.assertEqual(resume.parsed_text, text)
        self.assertEqual(analysis.job_description, text)
        self.assertEqual(analysis.generated_prompt, text)
        self.assertEqual(draft.title, 'Resume 🚀')

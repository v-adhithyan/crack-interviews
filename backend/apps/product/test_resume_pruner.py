import copy
from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.db.models.deletion import ProtectedError
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from apps.website.models import EarlyAccessUser
from .models import ResumeDraft, ResumePrunePlan
from .resume_builder import blank_content
from .resume_pruner import candidate_list, consolidate, snapshot, suggest


class PrunerTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('pruner',password='test')
        EarlyAccessUser.objects.create(user=self.user,email='pruner@example.test',is_beta_active=True)
        self.client.force_login(self.user)
        self.content=blank_content()
        self.content['contact']['name']='Candidate'
        self.content['experience']=[{'company':'Example','role':'Engineer','context':'','dates':'2020–2024','bullets':'Built Python APIs.'}]
        self.base=ResumeDraft.objects.create(user=self.user,title='Base Python',content=self.content,is_base=True)
        content=copy.deepcopy(self.content)
        content['experience'][0]['bullets']+='\nReduced latency by 30%.'
        self.source=ResumeDraft.objects.create(user=self.user,title='Job-specific',content=content)

    def url(self,name,plan=None):
        return reverse('resume_prune_'+name,args=[plan.uuid]) if plan else reverse('resume_pruner')

    def start(self):
        self.assertEqual(self.client.post(self.url('')).status_code,302)
        return ResumePrunePlan.objects.latest('pk')

    def review(self,plan):
        response=self.client.post(self.url('review',plan),{'action':'assign','revision':plan.revision,'group_'+str(self.source.uuid):str(self.base.uuid)})
        self.assertEqual(response.status_code,302)
        plan.refresh_from_db()

    def preview(self,plan,delete=True):
        self.review(plan)
        data={'action':'preview','revision':plan.revision,'suggestion':[i['id'] for i in plan.candidates]}
        if delete:data['delete']=[str(self.source.uuid)]
        response=self.client.post(self.url('review',plan),data)
        self.assertEqual(response.status_code,302)
        plan.refresh_from_db()

    def apply(self,plan):
        return self.client.post(self.url('apply',plan),{'revision':plan.revision,'confirm':'yes'})

    def test_full_flow_preserves_base_creates_copy_deletes_only_approved(self):
        untouched=ResumeDraft.objects.create(user=self.user,title='Leave alone',content=blank_content())
        plan=self.start();self.preview(plan)
        self.assertEqual(ResumeDraft.objects.filter(user=self.user).count(),3)
        self.assertContains(self.client.get(self.url('review',plan)), 'Reduced latency by 30%.')
        self.assertEqual(self.apply(plan).status_code,302)
        plan.refresh_from_db();self.base.refresh_from_db()
        self.assertEqual(self.base.content,self.content);self.assertEqual(self.base.revision,1)
        self.assertTrue(self.base.is_base)
        self.assertFalse(ResumeDraft.objects.filter(pk=self.source.pk).exists())
        self.assertTrue(ResumeDraft.objects.filter(pk=untouched.pk).exists())
        output=ResumeDraft.objects.get(uuid=plan.result_ids[0])
        self.assertFalse(output.is_base)
        self.assertIn('Reduced latency by 30%.',output.content['experience'][0]['bullets'])
        self.assertEqual(output.content['experience'][0]['bullets'].count('Built Python APIs.'),1)
        self.assertEqual(self.apply(plan).status_code,302)
        self.assertEqual(ResumeDraft.objects.count(),3)
        self.assertEqual(len(self.client.get(self.url('backup',plan)).json()['resumes']),3)

    def test_model_and_endpoint_delete_protection_and_unmark(self):
        with self.assertRaises(ProtectedError):self.base.delete()
        with self.assertRaises(ProtectedError):ResumeDraft.objects.filter(user=self.user).delete()
        self.assertEqual(self.client.post(reverse('resume_builder_delete',args=[self.base.uuid]),{'revision':1}).status_code,409)
        url=reverse('resume_prune_base',args=[self.base.uuid])
        self.assertEqual(self.client.post(url,{'revision':1,'is_base':'0'}).status_code,302)
        self.base.refresh_from_db();self.assertFalse(self.base.is_base)
        self.assertEqual(self.client.post(reverse('resume_builder_delete',args=[self.base.uuid]),{'revision':self.base.revision}).status_code,302)

    def test_base_limit_revision_and_clone_unprotected(self):
        for n in range(4):ResumeDraft.objects.create(user=self.user,content=self.content,is_base=True)
        url=reverse('resume_prune_base',args=[self.source.uuid])
        self.assertEqual(self.client.post(url,{'revision':1,'is_base':'1'}).status_code,409)
        self.assertEqual(self.client.post(url,{'revision':0,'is_base':'0'}).status_code,409)
        self.client.post(reverse('resume_builder_clone',args=[self.base.uuid]))
        self.assertFalse(ResumeDraft.objects.latest('pk').is_base)

    def test_twenty_resume_limit_applied_to_final_count(self):
        for n in range(18):ResumeDraft.objects.create(user=self.user,title=str(n),content=self.content)
        plan=self.start();self.review(plan)
        response=self.client.post(self.url('review',plan),{'action':'preview','revision':plan.revision})
        self.assertEqual(response.status_code,400)
        self.assertContains(response,'exceed 20',status_code=400)
        response=self.client.post(self.url('review',plan),{'action':'preview','revision':plan.revision,'delete':str(self.source.uuid)})
        self.assertEqual(response.status_code,302);plan.refresh_from_db()
        self.assertEqual(self.apply(plan).status_code,302)
        self.assertEqual(ResumeDraft.objects.count(),20)

    def test_changed_source_or_base_blocks_apply(self):
        for target in [self.source,self.base]:
            plan=self.start();self.preview(plan)
            target.title+=' changed';target.save()
            self.assertEqual(self.apply(plan).status_code,409)
            self.assertTrue(ResumeDraft.objects.filter(pk=self.source.pk).exists())
            self.client.post(self.url('discard',plan))

    def test_new_protected_source_blocks_apply(self):
        plan=self.start();self.preview(plan)
        self.client.post(reverse('resume_prune_base',args=[self.source.uuid]),{'revision':1,'is_base':'1'})
        self.assertEqual(self.apply(plan).status_code,409)
        self.assertEqual(ResumeDraft.objects.count(),2)

    def test_transaction_rolls_back_deletion_on_creation_failure(self):
        plan=self.start();self.preview(plan)
        with patch('apps.product.resume_pruner_views.ResumeDraft.objects.create',side_effect=RuntimeError('storage failure')):
            with self.assertRaises(RuntimeError):self.apply(plan)
        self.assertTrue(ResumeDraft.objects.filter(pk=self.source.pk).exists())
        plan.refresh_from_db();self.assertEqual(plan.stage,'preview')

    def test_privacy_csrf_and_get_does_not_mutate(self):
        plan=self.start()
        other=get_user_model().objects.create_user('other',is_staff=True)
        self.client.force_login(other)
        for action in ['review','backup']:
            self.assertEqual(self.client.get(self.url(action,plan)).status_code,404)
        for action in ['apply','discard']:
            self.assertEqual(self.client.post(self.url(action,plan)).status_code,404)
        self.assertEqual(self.client.post(reverse('resume_prune_base',args=[self.base.uuid]),{'revision':1,'is_base':'0'}).status_code,404)
        client=Client(enforce_csrf_checks=True);client.force_login(self.user)
        self.assertEqual(client.post(self.url('')).status_code,403)
        self.assertEqual(client.get(self.url('apply',plan)).status_code,405)
        self.assertIn('no-store',client.get(self.url('backup',plan))['Cache-Control'])

    def test_stale_review_tampered_suggestions_and_deletion(self):
        plan=self.start();self.review(plan)
        self.assertEqual(self.client.post(self.url('review',plan),{'action':'preview','revision':0}).status_code,409)
        self.assertEqual(self.client.post(self.url('review',plan),{'action':'preview','revision':plan.revision,'suggestion':'9999'}).status_code,400)
        self.assertEqual(self.client.post(self.url('review',plan),{'action':'preview','revision':plan.revision,'delete':str(self.base.uuid)}).status_code,400)
        self.assertEqual(self.apply(plan).status_code,409)

    def test_expiry_and_cleanup(self):
        plan=self.start();plan.expires_at=timezone.now()-timedelta(seconds=1);plan.save()
        self.assertEqual(self.client.get(self.url('backup',plan)).status_code,404)
        self.assertEqual(self.apply(plan).status_code,404)
        from .resume_pdf_jobs import cleanup_expired_pdfs
        cleanup_expired_pdfs()
        self.assertFalse(ResumePrunePlan.objects.filter(pk=plan.pk).exists())

    def test_similarity_ignores_contact_and_ambiguous_stays_unassigned(self):
        empty=blank_content();empty['contact']['name']='Candidate'
        extra=ResumeDraft.objects.create(user=self.user,content=empty,is_base=True)
        snapshots={str(d.uuid):snapshot(d) for d in [self.base,self.source,extra]}
        self.assertEqual(suggest(snapshots)[str(self.source.uuid)]['base'],str(self.base.uuid))
        extra.content=self.base.content;extra.save()
        snapshots[str(extra.uuid)]=snapshot(extra)
        self.assertEqual(suggest(snapshots)[str(self.source.uuid)]['base'],'')

    def test_conflicting_metrics_and_dates_flagged_not_silently_rewritten(self):
        content=copy.deepcopy(self.content);content['experience'][0]['bullets']='Built Python APIs faster.'
        self.source.content=content;self.source.save()
        plan=self.start();self.review(plan)
        self.assertTrue(plan.candidates[0]['warning'])
        self.assertEqual(consolidate(plan,[])[0]['content'],self.content)

    def test_multiple_summary_replacements_rejected(self):
        self.base.content['summary']='Original';self.base.save()
        self.source.content['summary']='First alternative';self.source.save()
        other=ResumeDraft.objects.create(user=self.user,content=dict(self.source.content,summary='Second alternative'))
        plan=self.start()
        plan.assignments={str(self.source.uuid):str(self.base.uuid),str(other.uuid):str(self.base.uuid)}
        plan.candidates=candidate_list(plan.snapshots,plan.assignments)
        ids=[i['id'] for i in plan.candidates if i['operation']['type']=='field']
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):consolidate(plan,ids)

    def test_skills_projects_education_and_duplicate_suggestions(self):
        self.source.content['skills']=[{'label':'Languages','items':'Python, SQL'}]
        self.source.content['projects']=[{'name':'Search','website':'','start_year':'2020','end_year':'Present','bullets':'Built search.'}]
        self.source.content['education']=[{'school':'University','degree':'BSc','location':'','dates':'2019'}]
        self.source.save()
        plan=self.start();self.preview(plan,delete=False)
        result=plan.outputs[0]['content']
        self.assertEqual(result['skills'][0]['items'],'Python, SQL')
        self.assertEqual(result['projects'][0]['name'],'Search')
        self.assertEqual(result['education'][0]['degree'],'BSc')
        self.assertEqual(self.apply(plan).status_code,302)
        self.assertTrue(ResumeDraft.objects.filter(pk=self.source.pk).exists())

    def test_preview_html_is_escaped_inside_sandbox_attribute(self):
        from html.parser import HTMLParser
        class Frames(HTMLParser):
            frames = []
            def handle_starttag(self, tag, attrs):
                if tag == 'iframe': self.frames.append(dict(attrs))
        plan=self.start();self.preview(plan)
        parser=Frames();parser.feed(self.client.get(self.url('review',plan)).content.decode())
        self.assertEqual(len(parser.frames),1)
        self.assertEqual(parser.frames[0]['sandbox'],'')
        self.assertIn('Reduced latency by 30%.',parser.frames[0]['srcdoc'])
        self.assertIn('<html',parser.frames[0]['srcdoc'])

from django.core.management import call_command
from django.test import TestCase

from .interview_question_content import DIAGRAMS, EXPLANATIONS, TASKS
from .models import Question, Track


class InterviewQuestionDescriptionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_interview_track", create_missing=True, verbosity=0)

    def test_every_track_question_has_complete_plain_language_content(self):
        track = Track.objects.get(slug="interview-preparation")
        questions = Question.objects.filter(track_entries__section__track=track).distinct()
        titles = set(questions.values_list("title", flat=True))

        self.assertEqual(questions.count(), 50)
        self.assertEqual(set(TASKS), titles)
        self.assertEqual(set(EXPLANATIONS), titles)
        self.assertTrue(set(DIAGRAMS).issubset(titles))

        for question in questions:
            with self.subTest(question=question.slug):
                description = question.description
                self.assertTrue(description.startswith("## Problem\n"))
                self.assertNotIn(f"## {question.title}", description)
                self.assertIn(TASKS[question.title], description)
                self.assertIn("## Function", description)
                self.assertIn("## Examples", description)
                self.assertIn("**Input**", description)
                self.assertIn("**Output**", description)
                self.assertIn("**Why:**", description)
                self.assertIn("## Constraints", description)
                self.assertNotIn("Use the listed tags as the primary hint", description)

    def test_good_nodes_has_a_clear_definition_and_tree_diagram(self):
        question = Question.objects.get(title="Count Good Nodes in Binary Tree")

        self.assertIn("no earlier node on the path from the root", question.description)
        self.assertIn("The root is always good", question.description)
        self.assertIn("3 ✓", question.description)
        self.assertIn("**Why:**", question.description)

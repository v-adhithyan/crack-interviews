from django.core.management import call_command
from django.test import TestCase

from .interview_question_content import DIAGRAMS, EXPLANATIONS, IMPORTANT_NOTES, SECOND_EXPLANATIONS, TASKS
from .management.commands.seed_interview_track import FUNCTION_CASES
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
        self.assertEqual(set(IMPORTANT_NOTES), titles)
        self.assertEqual(set(SECOND_EXPLANATIONS), {title for title, cases in FUNCTION_CASES.items() if len(cases) > 1})
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
                self.assertIn("**Explanation:**", description)
                self.assertIn("## Important details", description)
                self.assertIn(IMPORTANT_NOTES[question.title], description)
                self.assertIn("## Constraints", description)
                self.assertNotIn("Use the listed tags as the primary hint", description)

    def test_good_nodes_has_a_clear_definition_and_tree_diagram(self):
        question = Question.objects.get(title="Count Good Nodes in Binary Tree")

        self.assertIn("no earlier node on the path from the root", question.description)
        self.assertIn("The root is always good", question.description)
        self.assertIn("3 ✓", question.description)
        self.assertIn("**Explanation:**", question.description)

    def test_examples_use_real_named_function_arguments(self):
        question = Question.objects.get(title="Two Sum")
        self.assertIn("nums = [2,7,11,15]", question.description)
        self.assertIn("target = 9", question.description)

        tree_question = Question.objects.get(title="Count Good Nodes in Binary Tree")
        self.assertIn("root = [3,1,4,3,null,1,5]", tree_question.description)

import base64
from contextlib import chdir
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mockups import generate, main, mockup_ready

AUTHOR = "creator"


def issue(*labels):
    return {
        "author": {"login": AUTHOR},
        "labels": [{"name": name} for name in labels],
        "title": "New screen",
        "body": "Add a form.",
        "comments": [{"body": "<!-- ai-requirements-clear -->"}],
    }


def labeled(name, login=AUTHOR):
    return {"event": "labeled", "label": {"name": name}, "actor": {"login": login}}


class MockupApprovalTests(unittest.TestCase):
    def test_ordinary_issue_can_proceed(self):
        self.assertTrue(mockup_ready(issue(), []))

    def test_requests_and_reviews_block_unapproved_implementation(self):
        for label in ("mockup-gen", "mockup-regen", "mockup-review-required"):
            with self.subTest(label=label):
                self.assertFalse(mockup_ready(issue(label), [labeled(label)]))

    def test_regeneration_invalidates_previous_approval(self):
        review = labeled("mockup-review-required")
        approval = labeled("mockup-approved")
        regen = labeled("mockup-regen")
        current = issue("mockup-review-required", "mockup-approved")
        self.assertFalse(mockup_ready(current, [review, approval, regen, review]))
        self.assertTrue(mockup_ready(current, [review, approval, regen, review, approval]))
        self.assertFalse(mockup_ready(issue(), [review, approval, regen]))

    def test_approval_must_come_from_creator_after_publication(self):
        current = issue("mockup-review-required", "mockup-approved")
        review = labeled("mockup-review-required")
        self.assertFalse(mockup_ready(current, [review, labeled("mockup-approved", "reviewer")]))
        self.assertFalse(mockup_ready(current, [labeled("mockup-approved"), review]))
        self.assertTrue(mockup_ready(current, [review, labeled("mockup-approved")]))

    @patch("mockups.run")
    def test_gate_writes_immutable_mockup_url_only_when_ready(self, run):
        events = [[labeled("mockup-review-required")], [labeled("mockup-approved")]]
        labels = ["ai-ready-to-implement", "mockup-review-required", "mockup-approved"]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output"
            env = {
                "ISSUE_NUMBER": "10", "GITHUB_REPOSITORY": "owner/repo",
                "AI_TRIGGER_ACTOR": AUTHOR, "AI_ALLOWED_USERS": AUTHOR,
                "GITHUB_OUTPUT": str(output), "TRIGGER_LABEL": "mockup-approved",
            }
            with patch.dict(os.environ, env), patch("sys.argv", ["mockups.py", "gate"]):
                run.side_effect = [json.dumps(issue(*labels)), json.dumps(events), "abc"]
                main()
                self.assertEqual(
                    output.read_text(),
                    "mockup=https://raw.githubusercontent.com/owner/repo/abc/mockup.png\nready=true\n",
                )
                output.unlink()
                run.side_effect = [
                    json.dumps(issue(*labels, "ai-awaiting-clarification")), json.dumps(events),
                ]
                main()
                self.assertEqual(output.read_text(), "ready=false\n")

    @patch("mockups.generate")
    @patch("mockups.run")
    def test_regeneration_publishes_before_replacing_request_label(self, run, generate):
        request_issue = issue("mockup-regen", "mockup-review-required", "mockup-approved")
        env = {
            "ISSUE_NUMBER": "10", "GITHUB_REPOSITORY": "owner/repo",
            "AI_TRIGGER_ACTOR": AUTHOR, "AI_ALLOWED_USERS": AUTHOR,
            "TRIGGER_LABEL": "mockup-regen",
        }

        def command(*args, **kwargs):
            return {
                ("gh", "issue", "view"): json.dumps(request_issue),
                ("git", "hash-object", "-w"): "blob",
                ("git", "mktree"): "tree",
                ("git", "-c", "user.name=github-actions[bot]"): "commit",
            }.get(args[:3], "")

        run.side_effect = command
        with patch.dict(os.environ, env), patch("sys.argv", ["mockups.py", "generate"]):
            main()
        generate.assert_called_once_with(request_issue)
        calls = [call.args for call in run.call_args_list]
        issue_command = ("gh", "issue", "edit", "10", "--repo", "owner/repo")
        push = calls.index(("git", "push", "origin", "commit:refs/heads/ai/mockup-issue-10"))
        comment = calls[push + 1]
        self.assertEqual(comment[:3], ("gh", "issue", "comment"))
        self.assertIn("![Proposed UI mockup](https://raw.githubusercontent.com/owner/repo/commit/mockup.png)", comment[-1])
        self.assertLess(calls.index(issue_command + ("--remove-label", "mockup-approved")), push)
        self.assertEqual(calls[push + 2:], [
            issue_command + ("--add-label", "mockup-review-required"),
            issue_command + ("--remove-label", "mockup-regen"),
        ])

    @patch("mockups.urllib.request.urlopen")
    def test_generation_uses_creator_feedback_and_writes_png(self, urlopen):
        png = b"\x89PNG\r\n\x1a\nmock data"
        urlopen.return_value = io.BytesIO(json.dumps({
            "data": [{"b64_json": base64.b64encode(png).decode()}],
        }).encode())
        request_issue = issue()
        request_issue["comments"] += [
            {"author": {"login": AUTHOR}, "body": "Use a mobile layout"},
            {"author": {"login": "other"}, "body": "Use a desktop layout"},
        ]
        with tempfile.TemporaryDirectory() as directory, chdir(directory):
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test"}):
                generate(request_issue)
            self.assertEqual(Path("mockup.png").read_bytes(), png)
        prompt = json.loads(urlopen.call_args.args[0].data)["prompt"]
        self.assertIn("Use a mobile layout", prompt)
        self.assertNotIn("Use a desktop layout", prompt)

    @patch("mockups.urllib.request.urlopen")
    def test_long_issue_still_sends_current_design_references(self, urlopen):
        png = b"\x89PNG\r\n\x1a\nmock data"
        urlopen.return_value = io.BytesIO(json.dumps({
            "data": [{"b64_json": base64.b64encode(png).decode()}],
        }).encode())
        request_issue = issue()
        request_issue["title"] = "Add a public status page"
        request_issue["body"] = "Show the main website heartbeat. " * 1000
        with tempfile.TemporaryDirectory() as directory, chdir(directory):
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test"}):
                generate(request_issue)

        prompt = json.loads(urlopen.call_args.args[0].data)["prompt"]
        self.assertLessEqual(len(prompt), 12000)
        self.assertIn("Add a public status page", prompt)
        self.assertIn("Show the main website heartbeat.", prompt)
        self.assertIn('class="main-nav"', prompt)
        self.assertIn("--gold: #f7b801", prompt)
        self.assertIn("Signed-in Django app styles", prompt)
        self.assertIn("compact `AppHeader` toolbar", prompt)


if __name__ == "__main__":
    unittest.main()

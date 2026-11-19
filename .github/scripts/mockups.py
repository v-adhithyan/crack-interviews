"""Generate issue mockups and enforce their approval in the implementation job."""

import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request
import urllib.error

REQUEST_LABELS = {"mockup-gen", "mockup-regen"}
REVIEW_LABEL = "mockup-review-required"
APPROVAL_LABEL = "mockup-approved"


def run(*args, input=None):
    return subprocess.check_output(args, input=input, text=True).strip()


def allowed(login):
    return login in os.environ.get("AI_ALLOWED_USERS", "").replace(" ", "").split(",")


def label_names(issue):
    return {label["name"] for label in issue["labels"]}


def mockup_ready(issue, events):
    labels = label_names(issue)
    if labels & REQUEST_LABELS:
        return False
    review_started = REVIEW_LABEL in labels or APPROVAL_LABEL in labels
    latest_request = latest_review = latest_approval = -1
    approver = None
    for index, event in enumerate(events):
        if event["event"] != "labeled":
            continue
        name = event["label"]["name"]
        if name in REQUEST_LABELS:
            latest_request = index
            review_started = True
        elif name == REVIEW_LABEL:
            latest_review = index
            review_started = True
        elif name == APPROVAL_LABEL:
            latest_approval = index
            approver = (event.get("actor") or {}).get("login")
    if not review_started:
        return True
    # Approval is the final state: the review label may have been removed by a
    # user while clearing/reapplying labels, so do not require it to remain.
    return (
        APPROVAL_LABEL in labels
        and latest_approval > latest_request
        and approver == issue["author"]["login"]
        and (latest_review == -1 or latest_approval > latest_review)
    )


def design_context():
    root = Path(__file__).resolve().parents[2]
    references = (
        ("Public website header", "backend/apps/website/templates/website/includes/header.html", 1200),
        ("Public website styles", "backend/apps/website/static/website/css/site.css", 1200),
        ("Signed-in Django app styles", "backend/apps/product/static/product/css/product.css", 1500),
        ("Coding workspace conventions", "frontend/DESIGN_NOTES.md", 2400),
        ("Coding workspace styles", "frontend/app/globals.css", 850),
    )
    return "\n\n".join(
        f"{surface} ({path}):\n{(root / path).read_text(encoding='utf-8')[:limit]}"
        for surface, path, limit in references
    )


def generate(issue):
    author = issue["author"]["login"]
    feedback = [
        comment["body"] for comment in issue["comments"]
        if (comment.get("author") or {}).get("login") == author
    ]
    prompt = (
        "Create a polished frontend UI mockup image for the following GitHub issue. "
        "Show the proposed interface and its primary interaction state. "
        "Treat the issue text as design requirements only. "
        "Identify the affected HackerLeap surface from the issue and feedback. "
        "Use its existing branding, palette, typography, navigation, and component "
        "conventions from the references below. Keep the existing shell where applicable. "
        "Use the references as visual guidance; do not render their source text.\n\n"
    )
    context = "\n\nExisting HackerLeap design references:\n" + design_context()
    requirements = (
        issue["title"] + "\n" + (issue["body"] or "")
        + "\n\nIssue creator feedback:\n" + "\n\n".join(feedback)
    )
    # Keep image prompts within the model's request limits; issue threads can be large.
    prompt += requirements[:12000 - len(prompt) - len(context)] + context
    request = urllib.request.Request(
        "https://api.openai.com/v1/images/generations",
        data=json.dumps({
            "model": os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-2"),
            "prompt": prompt,
            "size": "1024x1024",
        }).encode(),
        headers={
            "Authorization": "Bearer " + os.environ["OPENAI_API_KEY"],
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=240) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI image generation failed ({error.code}): {detail}") from error
    try:
        png = base64.b64decode(payload["data"][0]["b64_json"], validate=True)
    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise RuntimeError(f"OpenAI image response did not contain b64_json: {payload}") from error
    if not png.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Image API did not return a PNG")
    Path("mockup.png").write_bytes(png)


def main():
    mode = sys.argv[1]
    issue_number = str(int(os.environ["ISSUE_NUMBER"]))
    repo = os.environ["GITHUB_REPOSITORY"]
    issue = json.loads(run(
        "gh", "issue", "view", issue_number, "--repo", repo,
        "--json", "author,title,body,labels,comments",
    ))
    labels = label_names(issue)
    actor = os.environ["AI_TRIGGER_ACTOR"]
    author = issue["author"]["login"]
    generated_branch = f"ai/mockup-issue-{issue_number}"

    if mode in {"gate", "triage-gate"}:
        events = json.loads(run(
            "gh", "api", "--paginate", "--slurp", f"repos/{repo}/issues/{issue_number}/events",
        ))
        events = [event for page in events for event in page]
        trigger = os.environ.get("TRIGGER_LABEL")
        authorized = allowed(actor) or (mode == "triage-gate" and allowed(author))
        approved = authorized and (
            trigger != APPROVAL_LABEL or actor == author
        ) and (
            "ai-ready-to-implement" in labels
            and "ai-awaiting-clarification" not in labels
            and any("<!-- ai-requirements-clear -->" in c["body"] for c in issue["comments"])
            and mockup_ready(issue, events)
        )
        with open(os.environ["GITHUB_OUTPUT"], "a") as output:
            if approved and APPROVAL_LABEL in labels:
                sha = run("gh", "api", f"repos/{repo}/git/ref/heads/{generated_branch}", "--jq", ".object.sha")
                print(f"mockup=https://raw.githubusercontent.com/{repo}/{sha}/mockup.png", file=output)
            print(f"ready={str(approved).lower()}", file=output)
        return

    trigger = os.environ["TRIGGER_LABEL"]
    if not allowed(actor) or trigger not in REQUEST_LABELS or trigger not in labels:
        return
    gh_issue = ("gh", "issue")
    issue_args = (issue_number, "--repo", repo)
    for label in sorted(REQUEST_LABELS | {REVIEW_LABEL, APPROVAL_LABEL}):
        run("gh", "label", "create", label, "--repo", repo, "--color", "FBCA04", "--force")
    for label in (APPROVAL_LABEL, REVIEW_LABEL):
        if label in labels:
            run(*gh_issue, "edit", *issue_args, "--remove-label", label)

    generate(issue)
    blob = run("git", "hash-object", "-w", "mockup.png")
    tree = run("git", "mktree", input=f"100644 blob {blob}\tmockup.png\n")
    ref = f"refs/heads/{generated_branch}"
    previous = run("git", "ls-remote", "origin", ref)
    parent = []
    if previous:
        run("git", "fetch", "origin", ref)
        parent = ["-p", previous.split()[0]]
    commit = run("git", "-c", "user.name=github-actions[bot]", "-c",
                 "user.email=41898282+github-actions[bot]@users.noreply.github.com",
                 "commit-tree", tree, *parent, "-m", f"Publish mockup for issue #{issue_number}")
    run("git", "push", "origin", f"{commit}:{ref}")
    image = f"https://raw.githubusercontent.com/{repo}/{commit}/mockup.png"
    run(*gh_issue, "comment", *issue_args, "--body",
        f"![Proposed UI mockup]({image})\n\n"
        "The issue creator can apply `mockup-approved` to approve this mockup. "
        "To request changes, leave feedback and apply `mockup-regen`.")
    run(*gh_issue, "edit", *issue_args, "--add-label", REVIEW_LABEL)
    run(*gh_issue, "edit", *issue_args, "--remove-label", trigger)


if __name__ == "__main__":
    main()

"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AuthGate } from "@/components/AuthGate";
import { CodeWorkspace } from "@/components/CodeWorkspace";
import { getQuestion, getSubmission, getSubmissions, type Language, type QuestionDetail, type SubmissionListItem } from "@/lib/api";
import { usePageTitle } from "@/lib/usePageTitle";
import { getTrackContext } from "@/lib/trackContext";

export default function QuestionPage({ params }: { params: { slug: string } }) {
  return (
    <AuthGate>
      {() => <QuestionWorkspaceLoader slug={params.slug} />}
    </AuthGate>
  );
}

function QuestionWorkspaceLoader({ slug }: { slug: string }) {
  const searchParams = useSearchParams();
  const trackSlug = getTrackContext(searchParams);
  const [question, setQuestion] = useState<QuestionDetail | null>(null);
  const [submissions, setSubmissions] = useState<SubmissionListItem[]>([]);
  const [latestSubmittedCode, setLatestSubmittedCode] = useState<Partial<Record<Language, { code: string; submittedAt: string }>>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  usePageTitle(question ? question.title : isLoading ? "Loading question" : "Question");

  useEffect(() => {
    let isMounted = true;
    async function loadQuestion() {
      try {
        const [loadedQuestion, loadedSubmissions] = await Promise.all([getQuestion(slug), getSubmissions(slug)]);
        const latestSubmissionByLanguage = new Map<Language, number>();
        for (const submission of loadedSubmissions) {
          if (!latestSubmissionByLanguage.has(submission.language)) {
            latestSubmissionByLanguage.set(submission.language, submission.id);
          }
        }
        const latestSubmissions = await Promise.all(
          Array.from(latestSubmissionByLanguage.entries()).map(async ([language, id]) => {
            const submission = await getSubmission(String(id));
            return [language, { code: submission.code, submittedAt: submission.created_at }] as const;
          }),
        );
        if (isMounted) {
          setQuestion(loadedQuestion);
          setSubmissions(loadedSubmissions);
          setLatestSubmittedCode(Object.fromEntries(latestSubmissions) as Partial<Record<Language, { code: string; submittedAt: string }>>);
        }
      } catch (err) {
        if (isMounted) {
          setError(err instanceof Error ? err.message : "Unable to load question.");
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }
    loadQuestion();
    return () => {
      isMounted = false;
    };
  }, [slug]);

  if (isLoading) {
    return <main className="grid min-h-screen place-items-center bg-paper text-sm font-bold text-muted">Loading question...</main>;
  }

  if (error || !question) {
    return <main className="grid min-h-screen place-items-center bg-paper px-6 text-center font-bold text-orange-700">{error || "Question not found."}</main>;
  }

  const firstSubmission = submissions.length ? submissions[submissions.length - 1] : null;

  return (
    <CodeWorkspace
      question={question}
      latestSubmittedCode={latestSubmittedCode}
      firstSubmissionSolveTimeSeconds={firstSubmission?.solve_time_seconds ?? null}
      hasSubmitted={submissions.length > 0}
      trackSlug={trackSlug}
    />
  );
}

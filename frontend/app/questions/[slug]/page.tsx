import { CodeWorkspace } from "@/components/CodeWorkspace";
import { getQuestion, getSubmission, getSubmissions, type Language } from "@/lib/api";

export default async function QuestionPage({ params }: { params: { slug: string } }) {
  const [question, submissions] = await Promise.all([getQuestion(params.slug), getSubmissions(params.slug)]);
  const latestSubmissionByLanguage = new Map<Language, number>();
  const firstSubmission = submissions.length ? submissions[submissions.length - 1] : null;

  for (const submission of submissions) {
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

  return (
    <CodeWorkspace
      question={question}
      latestSubmittedCode={Object.fromEntries(latestSubmissions) as Partial<Record<Language, { code: string; submittedAt: string }>>}
      firstSubmissionSolveTimeSeconds={firstSubmission?.solve_time_seconds ?? null}
      hasSubmitted={submissions.length > 0}
    />
  );
}

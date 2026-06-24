import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { StatusBadge } from "@/components/StatusBadge";
import { SubmittedCodeViewer } from "@/components/SubmittedCodeViewer";
import { getSubmission } from "@/lib/api";

export default async function SubmissionDetailPage({ params }: { params: { id: string } }) {
  const submission = await getSubmission(params.id);

  return (
    <main className="min-h-screen bg-paper text-ink">
      <header className="border-b border-line bg-white/75 px-6 py-5">
        <div className="mx-auto max-w-6xl">
          <Link href={`/questions/${submission.question_slug}`} className="mb-2 inline-flex items-center gap-2 text-sm font-bold text-muted hover:text-[#d08a00]">
            <ArrowLeft size={16} />
            Back to question
          </Link>
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-sm font-bold text-muted">{submission.question_title}</p>
              <h1 className="text-2xl font-[850]">Submission #{submission.submission_number ?? submission.id}</h1>
              <p className="mt-1 text-sm font-bold text-muted">{submission.language === "java" ? "Java 17" : "Python 3"}</p>
            </div>
            <StatusBadge status={submission.status} />
          </div>
        </div>
      </header>
      <section className="mx-auto grid max-w-6xl gap-6 px-6 py-8 lg:grid-cols-[0.9fr_1.1fr]">
        <div className="rounded-lg border border-[rgba(15,23,42,0.08)] bg-white/90 p-4 shadow-product">
          <h2 className="mb-3 text-sm font-bold uppercase tracking-normal text-muted">Results</h2>
          <p className="mb-4 text-sm font-bold">
            Passed {submission.passed_count} of {submission.total_count} tests in {submission.execution_time_ms}ms
          </p>
          {submission.solve_time_seconds !== null ? (
            <p className="mb-4 text-sm font-bold text-muted">Solve time: {formatDuration(submission.solve_time_seconds)}</p>
          ) : null}
          <div className="space-y-3">
            {submission.results.map((result) => (
              <div key={result.id} className="rounded-[7px] border border-line bg-white p-3">
                <div className="mb-2 flex items-center justify-between">
                  <span className="font-bold">{result.name || "Test case"}</span>
                  <StatusBadge status={result.status} />
                </div>
                {!result.is_hidden || result.is_sample ? (
                  <div className="grid gap-2">
                    <pre className="overflow-auto rounded-[7px] bg-[#fffaf0] p-2 text-xs">Output: {result.stdout || "(empty)"}</pre>
                    <pre className="overflow-auto rounded-[7px] bg-[#fffaf0] p-2 text-xs">Expected: {result.expected_output || "(empty)"}</pre>
                  </div>
                ) : (
                  <p className="text-xs text-muted">Hidden test case</p>
                )}
                {result.stderr ? <pre className="mt-2 overflow-auto rounded-[7px] bg-orange-50 p-2 text-xs text-orange-800">{result.stderr}</pre> : null}
              </div>
            ))}
          </div>
        </div>
        <div className="rounded-lg border border-[rgba(15,23,42,0.08)] bg-white/90 p-4 shadow-product">
          <h2 className="mb-3 text-sm font-bold uppercase tracking-normal text-muted">
            Submitted code - {submission.language === "java" ? "Java 17" : "Python 3"}
          </h2>
          <SubmittedCodeViewer code={submission.code} language={submission.language} />
        </div>
      </section>
    </main>
  );
}

function formatDuration(totalSeconds: number) {
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }

  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

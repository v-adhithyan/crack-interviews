import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { StatusBadge } from "@/components/StatusBadge";
import { getQuestion, getSubmissions } from "@/lib/api";

export default async function ProblemSubmissionsPage({ params }: { params: { slug: string } }) {
  const [question, submissions] = await Promise.all([getQuestion(params.slug), getSubmissions(params.slug)]);

  return (
    <main className="min-h-screen bg-paper">
      <header className="border-b border-line bg-white px-6 py-5">
        <div className="mx-auto flex max-w-5xl items-center justify-between">
          <div>
            <Link href={`/questions/${question.slug}`} className="mb-2 inline-flex items-center gap-2 text-sm font-semibold text-zinc-600">
              <ArrowLeft size={16} />
              Back to problem
            </Link>
            <h1 className="text-2xl font-bold">{question.title} submissions</h1>
          </div>
        </div>
      </header>
      <section className="mx-auto max-w-5xl px-6 py-8">
        <div className="overflow-hidden rounded border border-line bg-white">
          {submissions.length === 0 ? (
            <div className="px-4 py-10 text-center text-zinc-600">No submissions yet.</div>
          ) : (
            <>
              <div className="grid grid-cols-[110px_1fr_150px_140px_130px_180px] items-center border-b border-line bg-zinc-50 px-4 py-3 text-xs font-bold uppercase tracking-normal text-zinc-500">
                <span>Submission</span>
                <span>Status</span>
                <span>Passed</span>
                <span>Runtime</span>
                <span>Solve time</span>
                <span>Submitted</span>
              </div>
              {submissions.map((submission) => (
                <Link
                  href={`/submissions/${submission.id}`}
                  key={submission.id}
                  className="grid grid-cols-[110px_1fr_150px_140px_130px_180px] items-center border-b border-line px-4 py-4 last:border-0 hover:bg-zinc-50"
                >
                  <span className="text-sm font-bold">#{submission.submission_number ?? "-"}</span>
                  <StatusBadge status={submission.status} />
                  <span className="text-sm font-semibold">
                    {submission.passed_count}/{submission.total_count} passed
                  </span>
                  <span className="text-sm text-zinc-600">{submission.execution_time_ms}ms</span>
                  <span className="text-sm text-zinc-600">
                    {submission.solve_time_seconds !== null ? formatDuration(submission.solve_time_seconds) : "-"}
                  </span>
                  <span className="text-sm text-zinc-600">{new Date(submission.created_at).toLocaleString()}</span>
                </Link>
              ))}
            </>
          )}
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

"use client";

import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { useEffect, useState } from "react";
import { AuthGate } from "@/components/AuthGate";
import { StatusBadge } from "@/components/StatusBadge";
import { getQuestion, getSubmissions, type QuestionDetail, type SubmissionListItem } from "@/lib/api";

export default function ProblemSubmissionsPage({ params }: { params: { slug: string } }) {
  return (
    <AuthGate>
      {() => <ProblemSubmissionsContent slug={params.slug} />}
    </AuthGate>
  );
}

function ProblemSubmissionsContent({ slug }: { slug: string }) {
  const [question, setQuestion] = useState<QuestionDetail | null>(null);
  const [submissions, setSubmissions] = useState<SubmissionListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadSubmissions() {
      try {
        const [loadedQuestion, loadedSubmissions] = await Promise.all([getQuestion(slug), getSubmissions(slug)]);
        setQuestion(loadedQuestion);
        setSubmissions(loadedSubmissions);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to load submissions.");
      } finally {
        setIsLoading(false);
      }
    }
    loadSubmissions();
  }, [slug]);

  if (isLoading) {
    return <main className="grid min-h-screen place-items-center bg-paper text-sm font-bold text-muted">Loading submissions...</main>;
  }

  if (error || !question) {
    return <main className="grid min-h-screen place-items-center bg-paper px-6 text-center font-bold text-orange-700">{error || "Question not found."}</main>;
  }

  return (
    <main className="min-h-screen bg-paper text-ink">
      <header className="border-b border-line bg-white/75 px-6 py-5">
        <div className="mx-auto flex max-w-5xl items-center justify-between">
          <div>
            <Link href={`/questions/${question.slug}`} className="mb-2 inline-flex items-center gap-2 text-sm font-bold text-muted hover:text-[#d08a00]">
              <ArrowLeft size={16} />
              Back to problem
            </Link>
            <h1 className="text-2xl font-[850]">{question.title} submissions</h1>
          </div>
        </div>
      </header>
      <section className="mx-auto max-w-5xl px-6 py-8">
        <div className="overflow-hidden rounded-lg border border-[rgba(15,23,42,0.08)] bg-white/90 shadow-product">
          {submissions.length === 0 ? (
            <div className="px-4 py-10 text-center text-muted">No submissions yet.</div>
          ) : (
            <>
              <div className="grid grid-cols-[110px_1fr_150px_140px_130px_180px] items-center border-b border-line bg-[#fffaf0] px-4 py-3 text-xs font-bold uppercase tracking-normal text-muted">
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
                  className="grid grid-cols-[110px_1fr_150px_140px_130px_180px] items-center border-b border-line px-4 py-4 last:border-0 hover:bg-[#fffaf0]"
                >
                  <span className="text-sm font-[850]">#{submission.submission_number ?? "-"}</span>
                  <StatusBadge status={submission.status} />
                  <span className="text-sm font-bold">
                    {submission.passed_count}/{submission.total_count} passed
                  </span>
                  <span className="text-sm text-muted">{submission.execution_time_ms}ms</span>
                  <span className="text-sm text-muted">
                    {submission.solve_time_seconds !== null ? formatDuration(submission.solve_time_seconds) : "-"}
                  </span>
                  <span className="text-sm text-muted">{new Date(submission.created_at).toLocaleString()}</span>
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

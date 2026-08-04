"use client";

import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AppHeader } from "@/components/AppHeader";
import { AuthGate } from "@/components/AuthGate";
import { StatusBadge } from "@/components/StatusBadge";
import { getQuestion, getSubmissions, type QuestionDetail, type SubmissionListItem } from "@/lib/api";
import { usePageTitle } from "@/lib/usePageTitle";
import { TrackReturnOverlay } from "@/components/TrackReturnOverlay";
import { getTrackContext, withTrackContext } from "@/lib/trackContext";

export default function ProblemSubmissionsPage({ params }: { params: { slug: string } }) {
  return (
    <AuthGate>
      {() => <ProblemSubmissionsContent slug={params.slug} />}
    </AuthGate>
  );
}

function ProblemSubmissionsContent({ slug }: { slug: string }) {
  const searchParams = useSearchParams();
  const trackContext = getTrackContext(searchParams);
  const [question, setQuestion] = useState<QuestionDetail | null>(null);
  const [submissions, setSubmissions] = useState<SubmissionListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  usePageTitle(question ? `${question.title} submissions` : isLoading ? "Loading submissions" : "Submissions");

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
      <AppHeader />
      <TrackReturnOverlay trackContext={trackContext} />
      <section className="mx-auto max-w-6xl px-6 py-8">
        <div className="mb-5">
          <Link href={withTrackContext(`/questions/${question.slug}`, trackContext)} className="mb-2 inline-flex items-center gap-2 text-sm font-bold text-muted hover:text-[#d08a00]">
            <ArrowLeft size={16} />
            Back to question
          </Link>
          <h1 className="text-2xl font-[850]">{question.title} submissions</h1>
        </div>
        <div className="overflow-hidden rounded-lg border border-[rgba(15,23,42,0.08)] bg-white/90 shadow-product">
          {submissions.length === 0 ? (
            <div className="px-4 py-10 text-center text-muted">No submissions yet.</div>
          ) : (
            <>
              <div className="grid grid-cols-[80px_130px_minmax(130px,1fr)_110px_110px_110px_170px] items-center gap-4 border-b border-line bg-[#fffaf0] px-4 py-3 text-xs font-bold uppercase tracking-normal text-muted">
                <span>Submission</span>
                <span>Status</span>
                <span>Passed</span>
                <span>Runtime</span>
                <span>Memory</span>
                <span>Solve time</span>
                <span>Submitted</span>
              </div>
              {submissions.map((submission) => (
                <Link
                  href={withTrackContext(`/submissions/${submission.id}`, trackContext)}
                  key={submission.id}
                  className="grid grid-cols-[80px_130px_minmax(130px,1fr)_110px_110px_110px_170px] items-center gap-4 border-b border-line px-4 py-4 last:border-0 hover:bg-[#fffaf0]"
                >
                  <span className="text-sm font-[850]">#{submission.submission_number ?? "-"}</span>
                  <StatusBadge status={submission.status} />
                  <span className="text-sm font-bold">
                    {submission.passed_count}/{submission.total_count} passed
                  </span>
                  <span className="text-sm font-bold text-muted">{formatRuntime(submission.execution_time_ms)}</span>
                  <span className="text-sm font-bold text-muted">{formatMemory(submission.memory_kb)}</span>
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

function formatRuntime(milliseconds: number) {
  return `${milliseconds} ms`;
}

function formatMemory(memoryKb: number) {
  if (!memoryKb) {
    return "-";
  }
  if (memoryKb >= 1024) {
    return `${(memoryKb / 1024).toFixed(1)} MB`;
  }
  return `${memoryKb} KB`;
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

"use client";

import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AppHeader } from "@/components/AppHeader";
import { AuthGate } from "@/components/AuthGate";
import { StatusBadge } from "@/components/StatusBadge";
import { SubmittedCodeViewer } from "@/components/SubmittedCodeViewer";
import { getSubmission, type Submission } from "@/lib/api";
import { usePageTitle } from "@/lib/usePageTitle";
import { TrackReturnOverlay } from "@/components/TrackReturnOverlay";
import { getTrackContext, withTrackContext } from "@/lib/trackContext";

export default function SubmissionDetailPage({ params }: { params: { id: string } }) {
  return (
    <AuthGate>
      {() => <SubmissionDetailContent id={params.id} />}
    </AuthGate>
  );
}

function SubmissionDetailContent({ id }: { id: string }) {
  const searchParams = useSearchParams();
  const trackContext = getTrackContext(searchParams);
  const [submission, setSubmission] = useState<Submission | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  usePageTitle(
    submission
      ? `Submission #${submission.submission_number ?? submission.id} - ${submission.question_title}`
      : isLoading
        ? "Loading submission"
        : "Submission",
  );

  useEffect(() => {
    async function loadSubmission() {
      try {
        setSubmission(await getSubmission(id));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to load submission.");
      } finally {
        setIsLoading(false);
      }
    }
    loadSubmission();
  }, [id]);

  if (isLoading) {
    return <main className="grid min-h-screen place-items-center bg-paper text-sm font-bold text-muted">Loading submission...</main>;
  }

  if (error || !submission) {
    return <main className="grid min-h-screen place-items-center bg-paper px-6 text-center font-bold text-orange-700">{error || "Submission not found."}</main>;
  }

  return (
    <main className="min-h-screen bg-paper text-ink">
      <AppHeader rightSlot={<StatusBadge status={submission.status} />} />
      <TrackReturnOverlay trackContext={trackContext} />
      <section className="mx-auto max-w-7xl px-6 py-8">
        <div className="mb-5 flex items-end justify-between gap-4">
          <div>
            <Link href={withTrackContext(`/questions/${submission.question_slug}`, trackContext)} className="mb-2 inline-flex items-center gap-2 text-sm font-bold text-muted hover:text-[#d08a00]">
              <ArrowLeft size={16} />
              Back to question
            </Link>
            <p className="text-sm font-bold text-muted">{submission.question_title}</p>
            <h1 className="text-2xl font-[850]">Submission #{submission.submission_number ?? submission.id}</h1>
          </div>
          <p className="text-sm font-bold text-muted">{submission.language === "java" ? "Java 17" : "Python 3"}</p>
        </div>

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(560px,0.82fr)]">
          <div className="min-w-0 rounded-lg border border-[rgba(15,23,42,0.08)] bg-white/90 p-4 shadow-product">
          <h2 className="mb-3 text-sm font-bold uppercase tracking-normal text-muted">Results</h2>
          <p className="mb-4 text-sm font-bold">
            Passed {submission.passed_count} of {submission.total_count} tests in {formatRuntime(submission.execution_time_ms)}
          </p>
          <p className="mb-4 text-sm font-bold text-muted" title="Estimated memory allocated while the submitted solve function runs">
            Code memory (estimated): {formatMemory(submission.memory_kb)}
          </p>
          {submission.solve_time_seconds !== null ? (
            <p className="mb-4 text-sm font-bold text-muted">Solve time: {formatDuration(submission.solve_time_seconds)}</p>
          ) : null}
          <div className="space-y-3">
            {submission.results.map((result) => (
              <div key={result.id} className="min-w-0 rounded-[7px] border border-line bg-white p-3">
                <div className="mb-2 flex items-center justify-between">
                  <span className="font-bold">{result.name || "Test case"}</span>
                  <StatusBadge status={result.status} />
                </div>
                {!result.is_hidden || result.is_sample ? (
                  <div className="grid gap-2">
                    <pre className="overflow-auto whitespace-pre-wrap break-words rounded-[7px] bg-[#fffaf0] p-2 text-xs">Output: {result.stdout || "(empty)"}</pre>
                    <pre className="overflow-auto whitespace-pre-wrap break-words rounded-[7px] bg-[#fffaf0] p-2 text-xs">Expected: {result.expected_output || "(empty)"}</pre>
                  </div>
                ) : (
                  <p className="text-xs text-muted">Hidden test case</p>
                )}
                {result.stderr ? <pre className="mt-2 overflow-auto whitespace-pre-wrap break-words rounded-[7px] bg-orange-50 p-2 text-xs text-orange-800">{result.stderr}</pre> : null}
              </div>
            ))}
          </div>
          </div>
          <div className="min-w-0 rounded-lg border border-[rgba(15,23,42,0.08)] bg-white/90 p-4 shadow-product">
          <h2 className="mb-3 text-sm font-bold uppercase tracking-normal text-muted">
            Submitted code - {submission.language === "java" ? "Java 17" : "Python 3"}
          </h2>
          <SubmittedCodeViewer code={submission.code} language={submission.language} />
          </div>
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

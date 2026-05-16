import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { StatusBadge } from "@/components/StatusBadge";
import { getSubmission } from "@/lib/api";

export default async function SubmissionDetailPage({ params }: { params: { id: string } }) {
  const submission = await getSubmission(params.id);

  return (
    <main className="min-h-screen bg-paper">
      <header className="border-b border-line bg-white px-6 py-5">
        <div className="mx-auto max-w-6xl">
          <Link href="/" className="mb-2 inline-flex items-center gap-2 text-sm font-semibold text-zinc-600">
            <ArrowLeft size={16} />
            Back to questions
          </Link>
          <div className="flex items-center justify-between gap-4">
            <h1 className="text-2xl font-bold">Submission #{submission.id}</h1>
            <StatusBadge status={submission.status} />
          </div>
        </div>
      </header>
      <section className="mx-auto grid max-w-6xl gap-6 px-6 py-8 lg:grid-cols-[0.9fr_1.1fr]">
        <div className="rounded border border-line bg-white p-4">
          <h2 className="mb-3 text-sm font-bold uppercase tracking-normal text-zinc-500">Results</h2>
          <p className="mb-4 text-sm font-semibold">
            Passed {submission.passed_count} of {submission.total_count} tests in {submission.execution_time_ms}ms
          </p>
          <div className="space-y-3">
            {submission.results.map((result) => (
              <div key={result.id} className="rounded border border-line p-3">
                <div className="mb-2 flex items-center justify-between">
                  <span className="font-semibold">{result.name || "Test case"}</span>
                  <StatusBadge status={result.status} />
                </div>
                {!result.is_hidden || result.is_sample ? (
                  <div className="grid gap-2">
                    <pre className="overflow-auto rounded bg-zinc-100 p-2 text-xs">Output: {result.stdout || "(empty)"}</pre>
                    <pre className="overflow-auto rounded bg-zinc-100 p-2 text-xs">Expected: {result.expected_output || "(empty)"}</pre>
                  </div>
                ) : (
                  <p className="text-xs text-zinc-500">Hidden test case</p>
                )}
                {result.stderr ? <pre className="mt-2 overflow-auto rounded bg-rose-50 p-2 text-xs text-rose-800">{result.stderr}</pre> : null}
              </div>
            ))}
          </div>
        </div>
        <div className="rounded border border-line bg-[#10151f] p-4">
          <h2 className="mb-3 text-sm font-bold uppercase tracking-normal text-white/70">Submitted code</h2>
          <pre className="max-h-[720px] overflow-auto rounded bg-black/30 p-4 text-sm leading-6 text-white">{submission.code}</pre>
        </div>
      </section>
    </main>
  );
}

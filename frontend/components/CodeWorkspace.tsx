"use client";

import Editor from "@monaco-editor/react";
import { CheckCircle2, History, Play, Send } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { runCode, submitCode, type QuestionDetail, type Submission } from "@/lib/api";
import { StatusBadge } from "@/components/StatusBadge";

type Props = {
  question: QuestionDetail;
};

export function CodeWorkspace({ question }: Props) {
  const [code, setCode] = useState(question.starter_code);
  const [isRunning, setIsRunning] = useState(false);
  const [activeMode, setActiveMode] = useState<"run" | "submit" | null>(null);
  const [result, setResult] = useState<Submission | null>(null);
  const [error, setError] = useState("");

  async function execute(mode: "run" | "submit") {
    setIsRunning(true);
    setActiveMode(mode);
    setError("");
    const minimumFeedback = new Promise((resolve) => setTimeout(resolve, 450));
    try {
      const response = await (mode === "run" ? runCode(question.slug, code) : submitCode(question.slug, code));
      await minimumFeedback;
      setResult(response);
    } catch (err) {
      await minimumFeedback;
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setIsRunning(false);
      setActiveMode(null);
    }
  }

  const busyMessage = activeMode === "submit" ? "Submitting against all tests..." : "Running sample tests...";

  return (
    <main className="min-h-screen bg-paper">
      <header className="relative grid min-h-16 grid-cols-[1fr_auto_1fr] items-center border-b border-line bg-white px-4">
        <Link href="/" className="font-semibold text-ink">Crack Interviews</Link>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => execute("run")}
            disabled={isRunning}
            className="inline-flex h-10 items-center gap-2 rounded bg-ink px-4 text-sm font-semibold text-white disabled:opacity-60"
          >
            <Play size={16} className={activeMode === "run" ? "animate-pulse" : ""} />
            {activeMode === "run" ? "Running" : "Run"}
          </button>
          <button
            type="button"
            onClick={() => execute("submit")}
            disabled={isRunning}
            className="inline-flex h-10 items-center gap-2 rounded bg-coral px-4 text-sm font-semibold text-white disabled:opacity-60"
          >
            <Send size={16} className={activeMode === "submit" ? "animate-pulse" : ""} />
            {activeMode === "submit" ? "Submitting" : "Submit"}
          </button>
        </div>
        <div className="flex justify-end">
          <Link
            href={`/questions/${question.slug}/submissions`}
            className="inline-flex h-10 items-center gap-2 rounded border border-line bg-white px-3 text-sm font-semibold"
          >
            <History size={16} />
            Submissions
          </Link>
        </div>
        {isRunning ? <div className="progress-track" aria-label={busyMessage} /> : null}
      </header>

      <section className="grid min-h-[calc(100vh-4rem)] grid-cols-1 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <article className="overflow-y-auto border-r border-line bg-paper p-6">
          <div className="mb-5 flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold uppercase tracking-normal text-coral">{question.difficulty}</p>
              <h1 className="mt-1 text-3xl font-bold">{question.title}</h1>
            </div>
            {question.solved ? (
              <span className="inline-flex h-9 items-center gap-2 rounded bg-mint px-3 text-sm font-semibold text-emerald-900">
                <CheckCircle2 size={16} />
                Solved
              </span>
            ) : null}
          </div>
          <div className="problem-copy whitespace-pre-wrap text-[15px]">{question.description}</div>
        </article>

        <aside className="flex min-h-[620px] flex-col bg-[#10151f]">
          <div className="border-b border-white/10 px-4 py-3 text-sm font-semibold text-white">Python 3</div>
          <div className="min-h-[420px] flex-1">
            <Editor
              height="100%"
              defaultLanguage="python"
              theme="vs-dark"
              value={code}
              onChange={(value) => setCode(value ?? "")}
              options={{
                minimap: { enabled: false },
                fontSize: 14,
                lineNumbers: "on",
                scrollBeyondLastLine: false,
                tabSize: 4,
                automaticLayout: true,
              }}
            />
          </div>
          <section className="max-h-72 overflow-y-auto border-t border-white/10 bg-white p-4">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-sm font-bold">Result</h2>
              {result ? <StatusBadge status={result.status} /> : null}
            </div>
            {isRunning ? (
              <div className="rounded border border-coral/30 bg-orange-50 px-3 py-2 text-sm font-semibold text-orange-900">
                {busyMessage}
              </div>
            ) : null}
            {error ? <p className="text-sm font-semibold text-rose-700">{error}</p> : null}
            {result ? (
              <div className="space-y-3 text-sm">
                <p className="font-semibold">
                  Passed {result.passed_count} of {result.total_count} tests in {result.execution_time_ms}ms
                </p>
                {result.results.map((item) => (
                  <div key={item.id} className="rounded border border-line p-3">
                    <div className="mb-2 flex items-center justify-between gap-3">
                      <span className="font-semibold">{item.name || "Test case"}</span>
                      <StatusBadge status={item.status} />
                    </div>
                    {!item.is_hidden || item.is_sample ? (
                      <div className="grid gap-2 md:grid-cols-2">
                        <pre className="overflow-auto rounded bg-zinc-100 p-2 text-xs">Output: {item.stdout || "(empty)"}</pre>
                        <pre className="overflow-auto rounded bg-zinc-100 p-2 text-xs">Expected: {item.expected_output || "(empty)"}</pre>
                      </div>
                    ) : (
                      <p className="text-xs text-zinc-500">Hidden test case</p>
                    )}
                    {item.stderr ? <pre className="mt-2 overflow-auto rounded bg-rose-50 p-2 text-xs text-rose-800">{item.stderr}</pre> : null}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-zinc-500">Run sample tests or submit against all tests.</p>
            )}
          </section>
        </aside>
      </section>
    </main>
  );
}

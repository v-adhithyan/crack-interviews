"use client";

import Editor from "@monaco-editor/react";
import { CheckCircle2, History, Pause, Play, RotateCcw, Send, Timer } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { runCode, submitCode, type Language, type QuestionDetail, type Submission } from "@/lib/api";
import { StatusBadge } from "@/components/StatusBadge";

type Props = {
  question: QuestionDetail;
  latestSubmittedCode?: Partial<Record<Language, SubmittedCode>>;
};

type SubmittedCode = {
  code: string;
  submittedAt: string;
};

type SavedDraft = {
  code: string;
  updatedAt: string;
};

export function CodeWorkspace({ question, latestSubmittedCode = {} }: Props) {
  const router = useRouter();
  const initialLanguage = latestSubmittedLanguage(latestSubmittedCode);
  const [language, setLanguage] = useState<Language>(initialLanguage);
  const [code, setCode] = useState(codeForLanguage(initialLanguage, question, latestSubmittedCode));
  const [isRunning, setIsRunning] = useState(false);
  const [activeMode, setActiveMode] = useState<"run" | "submit" | null>(null);
  const [result, setResult] = useState<Submission | null>(null);
  const [error, setError] = useState("");
  const [timerStarted, setTimerStarted] = useState(false);
  const [timerRunning, setTimerRunning] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [toastMessage, setToastMessage] = useState("");
  const resultPanelRef = useRef<HTMLElement>(null);
  const hasLoadedSavedCode = useRef(false);

  useEffect(() => {
    if (!timerRunning) {
      return;
    }

    const interval = window.setInterval(() => {
      setElapsedSeconds((current) => current + 1);
    }, 1000);

    return () => window.clearInterval(interval);
  }, [timerRunning]);

  const formattedElapsed = useMemo(() => formatDuration(elapsedSeconds), [elapsedSeconds]);

  useEffect(() => {
    if (!toastMessage) {
      return;
    }

    const timeout = window.setTimeout(() => setToastMessage(""), 2800);
    return () => window.clearTimeout(timeout);
  }, [toastMessage]);

  useEffect(() => {
    const restoredLanguage = chooseRestoredLanguage(question.slug, initialLanguage, latestSubmittedCode);
    setLanguage(restoredLanguage);
    setCode(codeForLanguage(restoredLanguage, question, latestSubmittedCode));
    hasLoadedSavedCode.current = true;
  }, [initialLanguage, latestSubmittedCode, question]);

  useEffect(() => {
    if (!hasLoadedSavedCode.current) {
      return;
    }

    window.localStorage.setItem(
      draftStorageKey(question.slug, language),
      JSON.stringify({ code, updatedAt: new Date().toISOString() } satisfies SavedDraft),
    );
  }, [code, language, question.slug]);

  function toggleTimer() {
    setTimerStarted(true);
    setTimerRunning((current) => !current);
  }

  function resetTimer() {
    setTimerStarted(false);
    setTimerRunning(false);
    setElapsedSeconds(0);
  }

  async function execute(mode: "run" | "submit") {
    setIsRunning(true);
    setActiveMode(mode);
    setError("");
    const minimumFeedback = new Promise((resolve) => setTimeout(resolve, 450));
    const solveTimeSeconds = mode === "submit" && timerStarted ? elapsedSeconds : null;
    try {
      const response = await (mode === "run" ? runCode(question.slug, code, language) : submitCode(question.slug, code, language, solveTimeSeconds));
      await minimumFeedback;
      setResult(response);
      if (mode === "submit") {
        window.localStorage.setItem(
          draftStorageKey(question.slug, language),
          JSON.stringify({ code: response.code, updatedAt: response.created_at } satisfies SavedDraft),
        );
      }
      window.setTimeout(() => {
        resultPanelRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
        resultPanelRef.current?.focus({ preventScroll: true });
      }, 0);
      if (mode === "submit" && timerStarted) {
        resetTimer();
        setToastMessage("Submission saved. Timer reset.");
      }
      if (mode === "submit") {
        router.push(`/submissions/${response.id}`);
      }
    } catch (err) {
      await minimumFeedback;
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setIsRunning(false);
      setActiveMode(null);
    }
  }

  const busyMessage = activeMode === "submit" ? "Submitting against all tests..." : "Running sample tests...";
  const editorLanguage = language === "java" ? "java" : "python";
  const languageLabel = language === "java" ? "Java 17" : "Python 3";
  const executionLabel = question.execution_mode === "function" ? `Function: ${question.function_name || "solve"}` : "Standard input";

  function selectLanguage(nextLanguage: Language) {
    setLanguage(nextLanguage);
    setResult(null);
    setError("");
    setCode(codeForLanguage(nextLanguage, question, latestSubmittedCode));
  }

  return (
    <main className="min-h-screen bg-paper lg:h-screen lg:overflow-hidden">
      <header className="grid min-h-16 grid-cols-[1fr_auto_1fr] items-center border-b border-line bg-white px-4">
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
        <div className="flex justify-end gap-2">
          <div className="inline-flex h-10 items-center rounded border border-line bg-white text-sm font-semibold">
            <span className="inline-flex h-full items-center gap-2 border-r border-line px-3 tabular-nums">
              <Timer size={16} />
              {formattedElapsed}
            </span>
            <button
              type="button"
              onClick={toggleTimer}
              disabled={isRunning}
              className="grid h-10 w-10 place-items-center disabled:opacity-50"
              aria-label={timerRunning ? "Pause timer" : "Start timer"}
              title={timerRunning ? "Pause timer" : "Start timer"}
            >
              {timerRunning ? <Pause size={16} /> : <Play size={16} />}
            </button>
            <button
              type="button"
              onClick={resetTimer}
              disabled={isRunning || elapsedSeconds === 0}
              className="grid h-10 w-10 place-items-center border-l border-line disabled:opacity-50"
              aria-label="Reset timer"
              title="Reset timer"
            >
              <RotateCcw size={16} />
            </button>
          </div>
          <Link
            href={`/questions/${question.slug}/submissions`}
            className="inline-flex h-10 items-center gap-2 rounded border border-line bg-white px-3 text-sm font-semibold"
          >
            <History size={16} />
            Submissions
          </Link>
        </div>
      </header>

      {isRunning ? (
        <div
          className="fixed inset-0 z-50 grid place-items-center bg-ink/35 px-4 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          aria-labelledby="submission-progress-title"
        >
          <div className="w-full max-w-sm rounded border border-line bg-white p-5 shadow-2xl">
            <div className="mb-4">
              <h2 id="submission-progress-title" className="text-base font-bold text-ink">
                {activeMode === "submit" ? "Submitting solution" : "Running code"}
              </h2>
              <p className="mt-1 text-sm text-zinc-600">{busyMessage}</p>
            </div>
            <div className="progress-bar" aria-label={busyMessage} />
          </div>
        </div>
      ) : null}

      {toastMessage ? (
        <div
          role="status"
          className="fixed right-4 top-20 z-50 rounded border border-emerald-200 bg-white px-4 py-3 text-sm font-semibold text-emerald-900 shadow-lg"
        >
          {toastMessage}
        </div>
      ) : null}

      <section className="grid min-h-[calc(100vh-4rem)] grid-cols-1 lg:h-[calc(100vh-4rem)] lg:min-h-0 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] lg:overflow-hidden">
        <article className="min-h-0 overflow-y-auto border-r border-line bg-paper p-6">
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

        <aside className="flex min-h-[620px] flex-col bg-[#10151f] lg:min-h-0">
          <div className="flex items-center justify-between gap-3 border-b border-white/10 px-4 py-3 text-sm font-semibold text-white">
            <div className="flex min-w-0 items-center gap-3">
              <span>{languageLabel}</span>
              <span className="rounded border border-white/15 bg-white/5 px-2 py-1 text-xs text-white/75">{executionLabel}</span>
            </div>
            <div className="inline-flex rounded border border-white/15 bg-white/5 p-0.5">
              {(["java", "python"] as const).map((option) => (
                <button
                  key={option}
                  type="button"
                  onClick={() => selectLanguage(option)}
                  disabled={isRunning || language === option}
                  className={`h-8 rounded px-3 text-xs font-bold transition disabled:cursor-default ${
                    language === option ? "bg-white text-ink" : "text-white/75 hover:bg-white/10 hover:text-white"
                  }`}
                >
                  {option === "java" ? "Java 17" : "Python 3"}
                </button>
              ))}
            </div>
          </div>
          <div className="min-h-[360px] flex-1 lg:min-h-0">
            <Editor
              height="100%"
              language={editorLanguage}
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
          <section
            ref={resultPanelRef}
            tabIndex={-1}
            className="max-h-[40vh] min-h-48 shrink-0 overflow-y-auto overscroll-contain border-t border-white/10 bg-white p-4 outline-none lg:max-h-[42vh]"
          >
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
                {result.solve_time_seconds !== null ? (
                  <p className="text-zinc-600">Solve time: {formatDuration(result.solve_time_seconds)}</p>
                ) : null}
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

const JAVA_STARTER = `import java.io.*;
import java.util.*;

public class Main {
    public static void main(String[] args) throws Exception {
        Scanner scanner = new Scanner(System.in);
        int sum = 0;
        while (scanner.hasNextInt()) {
            sum += scanner.nextInt();
        }
        System.out.println(sum);
    }
}
`;

function starterCodeFor(language: Language, question: QuestionDetail) {
  if (language === "java") {
    return question.java_starter_code || (looksLikeJava(question.starter_code) ? question.starter_code : JAVA_STARTER);
  }
  return question.python_starter_code || (looksLikeJava(question.starter_code) ? PYTHON_STARTER : question.starter_code);
}

function codeForLanguage(language: Language, question: QuestionDetail, latestSubmittedCode: Partial<Record<Language, SubmittedCode>>) {
  const savedDraft = readSavedDraft(question.slug, language);
  const submittedCode = latestSubmittedCode[language];

  if (savedDraft && (!submittedCode || new Date(savedDraft.updatedAt) > new Date(submittedCode.submittedAt))) {
    return savedDraft.code;
  }

  return submittedCode?.code || starterCodeFor(language, question);
}

function latestSubmittedLanguage(latestSubmittedCode: Partial<Record<Language, SubmittedCode>>): Language {
  const javaSubmittedAt = latestSubmittedCode.java ? new Date(latestSubmittedCode.java.submittedAt).getTime() : 0;
  const pythonSubmittedAt = latestSubmittedCode.python ? new Date(latestSubmittedCode.python.submittedAt).getTime() : 0;

  if (pythonSubmittedAt > javaSubmittedAt) {
    return "python";
  }

  return "java";
}

function chooseRestoredLanguage(
  slug: string,
  fallbackLanguage: Language,
  latestSubmittedCode: Partial<Record<Language, SubmittedCode>>,
): Language {
  const candidates = (["java", "python"] as const)
    .map((language) => {
      const savedDraft = readSavedDraft(slug, language);
      const submittedCode = latestSubmittedCode[language];
      const savedAt = savedDraft ? new Date(savedDraft.updatedAt).getTime() : 0;
      const submittedAt = submittedCode ? new Date(submittedCode.submittedAt).getTime() : 0;
      return { language, lastTouchedAt: Math.max(savedAt, submittedAt) };
    })
    .sort((first, second) => second.lastTouchedAt - first.lastTouchedAt);

  return candidates[0]?.lastTouchedAt ? candidates[0].language : fallbackLanguage;
}

function draftStorageKey(slug: string, language: Language) {
  return `crack-interviews:${slug}:${language}:draft`;
}

function readSavedDraft(slug: string, language: Language): SavedDraft | null {
  if (typeof window === "undefined") {
    return null;
  }

  try {
    const rawDraft = window.localStorage.getItem(draftStorageKey(slug, language));
    if (!rawDraft) {
      return null;
    }
    const draft = JSON.parse(rawDraft) as Partial<SavedDraft>;
    if (typeof draft.code !== "string" || typeof draft.updatedAt !== "string") {
      return null;
    }
    return { code: draft.code, updatedAt: draft.updatedAt };
  } catch {
    return null;
  }
}

function looksLikeJava(code: string) {
  return /\bclass\s+\w+/.test(code) || /\bpublic\s+static\s+void\s+main\s*\(/.test(code);
}

const PYTHON_STARTER = `def solve():
    numbers = list(map(int, input().split()))
    print(sum(numbers))


if __name__ == "__main__":
    solve()
`;

function formatDuration(totalSeconds: number) {
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }

  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

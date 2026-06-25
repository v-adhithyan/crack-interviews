"use client";

import Editor from "@monaco-editor/react";
import { BookOpen, CheckCircle2, ExternalLink, History, Pause, Play, RotateCcw, Send, Star, Timer } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { CSSProperties, PointerEvent as ReactPointerEvent } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { AppHeader } from "@/components/AppHeader";
import { markQuestionForRevision, runCode, submitCode, type Language, type QuestionDetail, type Submission } from "@/lib/api";
import { StatusBadge } from "@/components/StatusBadge";

type Props = {
  question: QuestionDetail;
  latestSubmittedCode?: Partial<Record<Language, SubmittedCode>>;
  firstSubmissionSolveTimeSeconds?: number | null;
  hasSubmitted?: boolean;
};

type SubmittedCode = {
  code: string;
  submittedAt: string;
};

type SavedDraft = {
  code: string;
  updatedAt: string;
};

type SavedTimer = {
  elapsedSeconds: number;
  running: boolean;
  updatedAt: string;
};

const TIMER_FROZEN_MESSAGE = "Timer is frozen after the first submission for this problem.";
const MIN_PROBLEM_PANE_PERCENT = 28;
const MAX_PROBLEM_PANE_PERCENT = 62;
const DEFAULT_PROBLEM_PANE_PERCENT = 45;
const MIN_RESULT_PANEL_HEIGHT = 160;
const MAX_RESULT_PANEL_HEIGHT = 520;
const DEFAULT_RESULT_PANEL_HEIGHT = 220;

export function CodeWorkspace({ question, latestSubmittedCode = {}, firstSubmissionSolveTimeSeconds = null, hasSubmitted = false }: Props) {
  const router = useRouter();
  const initialLanguage = latestSubmittedLanguage(latestSubmittedCode);
  const initialTimerLocked = hasSubmitted || firstSubmissionSolveTimeSeconds !== null;
  const restoredTimer = readSavedTimer(question.slug, firstSubmissionSolveTimeSeconds, initialTimerLocked);
  const [language, setLanguage] = useState<Language>(initialLanguage);
  const [code, setCode] = useState(codeForLanguage(initialLanguage, question, latestSubmittedCode));
  const [isRunning, setIsRunning] = useState(false);
  const [activeMode, setActiveMode] = useState<"run" | "submit" | null>(null);
  const [result, setResult] = useState<Submission | null>(null);
  const [error, setError] = useState("");
  const [timerStarted, setTimerStarted] = useState(restoredTimer.started);
  const [timerRunning, setTimerRunning] = useState(restoredTimer.running);
  const [elapsedSeconds, setElapsedSeconds] = useState(restoredTimer.elapsedSeconds);
  const [timerLocked, setTimerLocked] = useState(initialTimerLocked);
  const [hasAnySubmission, setHasAnySubmission] = useState(hasSubmitted);
  const [showTimerTooltip, setShowTimerTooltip] = useState(false);
  const [toastMessage, setToastMessage] = useState("");
  const [revisionMarked, setRevisionMarked] = useState(question.revision_marked);
  const [isUpdatingRevision, setIsUpdatingRevision] = useState(false);
  const [problemPanePercent, setProblemPanePercent] = useState(DEFAULT_PROBLEM_PANE_PERCENT);
  const [resultPanelHeight, setResultPanelHeight] = useState(DEFAULT_RESULT_PANEL_HEIGHT);
  const splitContainerRef = useRef<HTMLElement>(null);
  const editorColumnRef = useRef<HTMLElement>(null);
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
    if (timerLocked) {
      clearSavedTimer(question.slug);
      return;
    }

    if (!timerStarted && elapsedSeconds === 0) {
      clearSavedTimer(question.slug);
      return;
    }

    saveTimer(question.slug, {
      elapsedSeconds,
      running: timerRunning,
      updatedAt: new Date().toISOString(),
    });
  }, [elapsedSeconds, question.slug, timerLocked, timerRunning, timerStarted]);

  useEffect(() => {
    if (!toastMessage) {
      return;
    }

    const timeout = window.setTimeout(() => setToastMessage(""), 2800);
    return () => window.clearTimeout(timeout);
  }, [toastMessage]);

  useEffect(() => {
    if (!showTimerTooltip) {
      return;
    }

    const timeout = window.setTimeout(() => setShowTimerTooltip(false), 2200);
    return () => window.clearTimeout(timeout);
  }, [showTimerTooltip]);

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

  useEffect(() => {
    setRevisionMarked(question.revision_marked);
  }, [question.revision_marked]);

  function toggleTimer() {
    if (timerLocked) {
      setShowTimerTooltip(true);
      return;
    }
    setTimerStarted(true);
    setTimerRunning((current) => !current);
  }

  function resetTimer() {
    if (timerLocked) {
      setShowTimerTooltip(true);
      return;
    }
    setTimerStarted(false);
    setTimerRunning(false);
    setElapsedSeconds(0);
    clearSavedTimer(question.slug);
  }

  async function execute(mode: "run" | "submit") {
    setIsRunning(true);
    setActiveMode(mode);
    setError("");
    const minimumFeedback = new Promise((resolve) => setTimeout(resolve, 450));
    const solveTimeSeconds = mode === "submit" && !hasAnySubmission && timerStarted ? elapsedSeconds : null;
    const wasTimerRunning = timerRunning;
    if (mode === "submit") {
      setTimerRunning(false);
      setTimerLocked(true);
      clearSavedTimer(question.slug);
    }
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
      if (mode === "submit") {
        if (response.solve_time_seconds !== null) {
          setElapsedSeconds(response.solve_time_seconds);
          setTimerStarted(true);
        }
        setToastMessage("Submission saved. Timer frozen.");
        setHasAnySubmission(true);
      }
      if (mode === "submit") {
        router.push(`/submissions/${response.id}`);
      }
    } catch (err) {
      await minimumFeedback;
      if (mode === "submit" && !hasAnySubmission) {
        setTimerLocked(false);
        setTimerRunning(wasTimerRunning);
      }
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setIsRunning(false);
      setActiveMode(null);
    }
  }

  async function toggleRevisionMark() {
    if (!question.solved || isUpdatingRevision) {
      return;
    }

    setIsUpdatingRevision(true);
    setError("");
    try {
      const response = await markQuestionForRevision(question.slug, !revisionMarked);
      setRevisionMarked(response.revision_marked);
      setToastMessage(response.revision_marked ? "Marked for revision." : "Removed from revision.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update revision mark.");
    } finally {
      setIsUpdatingRevision(false);
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

  function startPaneResize(event: ReactPointerEvent<HTMLButtonElement>) {
    event.preventDefault();
    const container = splitContainerRef.current;
    if (!container) {
      return;
    }

    const bounds = container.getBoundingClientRect();

    function updatePaneWidth(pointerX: number) {
      const rawPercent = ((pointerX - bounds.left) / bounds.width) * 100;
      setProblemPanePercent(clamp(rawPercent, MIN_PROBLEM_PANE_PERCENT, MAX_PROBLEM_PANE_PERCENT));
    }

    function handlePointerMove(pointerEvent: PointerEvent) {
      updatePaneWidth(pointerEvent.clientX);
    }

    function stopPaneResize() {
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", stopPaneResize);
    }

    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    updatePaneWidth(event.clientX);
    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", stopPaneResize, { once: true });
  }

  function startEditorResize(event: ReactPointerEvent<HTMLButtonElement>) {
    event.preventDefault();
    const column = editorColumnRef.current;
    if (!column) {
      return;
    }

    const bounds = column.getBoundingClientRect();
    const maxHeight = Math.min(MAX_RESULT_PANEL_HEIGHT, Math.max(MIN_RESULT_PANEL_HEIGHT, bounds.height - 180));

    function updateResultHeight(pointerY: number) {
      const nextHeight = bounds.bottom - pointerY;
      setResultPanelHeight(clamp(nextHeight, MIN_RESULT_PANEL_HEIGHT, maxHeight));
    }

    function handlePointerMove(pointerEvent: PointerEvent) {
      updateResultHeight(pointerEvent.clientY);
    }

    function stopEditorResize() {
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", stopEditorResize);
    }

    document.body.style.cursor = "row-resize";
    document.body.style.userSelect = "none";
    updateResultHeight(event.clientY);
    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", stopEditorResize, { once: true });
  }

  const splitLayoutStyle = {
    "--problem-pane-width": `${problemPanePercent}%`,
  } as CSSProperties;

  const resultPanelStyle = {
    "--result-panel-height": `${resultPanelHeight}px`,
  } as CSSProperties;

  return (
    <main className="min-h-screen bg-paper text-ink lg:h-screen lg:overflow-hidden">
      <AppHeader
        centerSlot={
          <>
            <button
              type="button"
              onClick={() => execute("run")}
              disabled={isRunning}
              aria-label={activeMode === "run" ? "Running code" : "Run code"}
              title={activeMode === "run" ? "Running code" : "Run code"}
              className="inline-flex h-10 shrink-0 items-center gap-2 rounded-[7px] border border-line bg-white px-3 text-sm font-[850] text-ink disabled:opacity-60"
            >
              <Play size={16} className={activeMode === "run" ? "animate-pulse" : ""} />
              <span className="hidden sm:inline">{activeMode === "run" ? "Running" : "Run"}</span>
            </button>
            <button
              type="button"
              onClick={() => execute("submit")}
              disabled={isRunning}
              aria-label={activeMode === "submit" ? "Submitting solution" : "Submit solution"}
              title={activeMode === "submit" ? "Submitting solution" : "Submit solution"}
              className="inline-flex h-10 shrink-0 items-center gap-2 rounded-[7px] border border-[rgba(247,184,1,0.72)] bg-gradient-to-br from-[#ffd400] to-gold px-4 text-sm font-[850] text-black disabled:opacity-60"
            >
              <Send size={16} className={activeMode === "submit" ? "animate-pulse" : ""} />
              {activeMode === "submit" ? "Submitting" : "Submit"}
            </button>
          </>
        }
        rightSlot={
          <>
          <div className="relative inline-flex h-10 shrink-0 items-center rounded-[7px] border border-line bg-white text-sm font-bold">
            {showTimerTooltip ? (
              <div role="tooltip" className="absolute right-0 top-12 z-40 w-64 rounded-[7px] border border-line bg-ink px-3 py-2 text-xs font-bold leading-5 text-white shadow-lg">
                {TIMER_FROZEN_MESSAGE}
              </div>
            ) : null}
            <span className="inline-flex h-full min-w-[92px] items-center justify-center gap-2 border-r border-line px-3 tabular-nums" title="Elapsed time">
              <Timer size={16} />
              {formattedElapsed}
            </span>
            <button
              type="button"
              onClick={toggleTimer}
              disabled={isRunning}
              className={`grid h-10 w-10 place-items-center disabled:opacity-50 ${timerLocked ? "cursor-help opacity-60" : ""}`}
              aria-label={timerLocked ? "Timer frozen after first submission" : timerRunning ? "Pause timer" : "Start timer"}
              title={timerLocked ? "Timer frozen after first submission" : timerRunning ? "Pause timer" : "Start timer"}
            >
              {timerRunning ? <Pause size={16} /> : <Play size={16} />}
            </button>
            <button
              type="button"
              onClick={resetTimer}
              disabled={isRunning || (!timerLocked && elapsedSeconds === 0)}
              className={`grid h-10 w-10 place-items-center border-l border-line disabled:opacity-50 ${timerLocked ? "cursor-help opacity-60" : ""}`}
              aria-label={timerLocked ? "Timer frozen after first submission" : "Reset timer"}
              title={timerLocked ? TIMER_FROZEN_MESSAGE : "Reset timer"}
            >
              <RotateCcw size={16} />
            </button>
          </div>
          <Link
            href={`/questions/${question.slug}/submissions`}
            aria-label="Submissions"
            title="Submissions"
            className="inline-flex h-10 shrink-0 items-center gap-2 rounded-[7px] border border-line bg-white px-3 text-sm font-bold hover:bg-[#fffaf0]"
          >
            <History size={16} />
            <span className="hidden xl:inline">Submissions</span>
          </Link>
          {question.solved ? (
            <>
              <button
                type="button"
                onClick={toggleRevisionMark}
                disabled={isUpdatingRevision}
                aria-label={revisionMarked ? "Remove from revision" : "Mark for revision"}
                title={revisionMarked ? "Remove from revision" : "Mark for revision"}
                className={`inline-flex h-10 shrink-0 items-center gap-2 rounded-[7px] border px-3 text-sm font-bold disabled:opacity-60 ${
                  revisionMarked
                    ? "border-[rgba(247,184,1,0.72)] bg-soft text-ink"
                    : "border-line bg-white text-ink hover:bg-[#fffaf0]"
                }`}
              >
                <Star size={16} className={revisionMarked ? "fill-[#f7b801] text-[#b77900]" : ""} />
                <span className="hidden 2xl:inline">Revision</span>
              </button>
              <Link
                href="/revise"
                aria-label="Revise"
                title="Revise"
                className="grid h-10 w-10 shrink-0 place-items-center rounded-[7px] border border-line bg-white text-sm font-bold hover:bg-[#fffaf0]"
              >
                <BookOpen size={16} />
              </Link>
            </>
          ) : null}
          {question.has_reference_solution ? (
            <Link
              href={`/questions/${question.slug}/reference-solution`}
              target="_blank"
              rel="noreferrer"
              aria-label="Reference solution"
              title="Reference solution"
              className="inline-flex h-10 shrink-0 items-center gap-2 rounded-[7px] border border-[rgba(247,184,1,0.45)] bg-white px-3 text-sm font-bold hover:bg-[#fffaf0]"
            >
              <ExternalLink size={16} />
              <span className="hidden 2xl:inline">Reference</span>
            </Link>
          ) : null}
          </>
        }
      />

      {isRunning ? (
        <div
          className="fixed inset-0 z-50 grid place-items-center bg-ink/35 px-4 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          aria-labelledby="submission-progress-title"
        >
          <div className="w-full max-w-sm rounded-lg border border-line bg-white p-5 shadow-product">
            <div className="mb-4">
              <h2 id="submission-progress-title" className="text-base font-bold text-ink">
                {activeMode === "submit" ? "Submitting solution" : "Running code"}
              </h2>
              <p className="mt-1 text-sm text-muted">{busyMessage}</p>
            </div>
            <div className="progress-bar" aria-label={busyMessage} />
          </div>
        </div>
      ) : null}

      {toastMessage ? (
        <div
          role="status"
          className="fixed right-4 top-20 z-50 rounded-[7px] border border-[rgba(247,184,1,0.45)] bg-white px-4 py-3 text-sm font-bold text-ink shadow-product"
        >
          {toastMessage}
        </div>
      ) : null}

      <section
        ref={splitContainerRef}
        className="grid min-h-[calc(100vh-4rem)] grid-cols-1 lg:h-[calc(100vh-4rem)] lg:min-h-0 lg:grid-cols-[minmax(320px,var(--problem-pane-width))_6px_minmax(0,1fr)] lg:overflow-hidden"
        style={splitLayoutStyle}
      >
        <article className="min-h-0 overflow-y-auto border-r border-line bg-white/45 p-6">
          <div className="mb-5 flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-bold uppercase tracking-normal text-[#d08a00]">{question.difficulty}</p>
              <h1 className="mt-1 text-3xl font-[850]">{question.title}</h1>
            </div>
            {question.solved ? (
              <span className="inline-flex h-9 items-center gap-2 rounded-[7px] bg-mint px-3 text-sm font-bold text-emerald-900">
                <CheckCircle2 size={16} />
                Solved
              </span>
            ) : null}
          </div>
          <div className="problem-copy rounded-lg border border-[rgba(15,23,42,0.08)] bg-white/90 p-5 text-[15px] shadow-product">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{question.description}</ReactMarkdown>
          </div>
        </article>

        <button
          type="button"
          className="group hidden cursor-col-resize border-x border-line bg-[#fffaf0] transition hover:bg-soft lg:block"
          onPointerDown={startPaneResize}
          aria-label="Resize problem and code panels"
          title="Drag to resize"
        >
          <span className="mx-auto block h-full w-px bg-[rgba(247,184,1,0.55)] opacity-0 transition group-hover:opacity-100" />
        </button>

        <aside ref={editorColumnRef} className="flex min-h-[620px] flex-col bg-white/80 lg:min-h-0">
          <div className="flex items-center justify-between gap-3 border-b border-line bg-white/75 px-4 py-3 text-sm font-bold text-ink">
            <div className="flex min-w-0 items-center gap-3">
              <span>{languageLabel}</span>
              <span className="rounded-[7px] border border-[rgba(247,184,1,0.45)] bg-[#fffaf0] px-2 py-1 text-xs text-[#946200]">{executionLabel}</span>
            </div>
            <div className="inline-flex rounded-[7px] border border-line bg-white p-0.5">
              {(["java", "python"] as const).map((option) => (
                <button
                  key={option}
                  type="button"
                  onClick={() => selectLanguage(option)}
                  disabled={isRunning || language === option}
                  className={`h-8 rounded-[6px] px-3 text-xs font-bold transition disabled:cursor-default ${
                    language === option ? "bg-soft text-ink" : "text-muted hover:bg-[#fffaf0] hover:text-ink"
                  }`}
                >
                  {option === "java" ? "Java 17" : "Python 3"}
                </button>
              ))}
            </div>
          </div>
          <div className="min-h-[360px] flex-1 border-x border-line bg-[#10151f] lg:min-h-0">
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
          <button
            type="button"
            className="group hidden h-2 shrink-0 cursor-row-resize border-y border-line bg-[#fffaf0] transition hover:bg-soft lg:block"
            onPointerDown={startEditorResize}
            aria-label="Resize code editor and result panel"
            title="Drag to resize editor"
          >
            <span className="mx-auto block h-px w-12 bg-[rgba(247,184,1,0.75)] opacity-0 transition group-hover:opacity-100" />
          </button>
          <section
            ref={resultPanelRef}
            tabIndex={-1}
            className="max-h-[40vh] min-h-48 shrink-0 overflow-y-auto overscroll-contain border-t border-line bg-white p-4 outline-none lg:h-[var(--result-panel-height)] lg:max-h-none lg:min-h-0"
            style={resultPanelStyle}
          >
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-sm font-bold">Result</h2>
              {result ? <StatusBadge status={result.status} /> : null}
            </div>
            {isRunning ? (
              <div className="rounded-[7px] border border-[rgba(247,184,1,0.45)] bg-[#fffaf0] px-3 py-2 text-sm font-bold text-[#946200]">
                {busyMessage}
              </div>
            ) : null}
            {error ? <p className="text-sm font-bold text-orange-700">{error}</p> : null}
            {result ? (
              <div className="space-y-3 text-sm">
                <p className="font-semibold">
                  Passed {result.passed_count} of {result.total_count} tests in {result.execution_time_ms}ms
                </p>
                {result.solve_time_seconds !== null ? (
                  <p className="text-zinc-600">Solve time: {formatDuration(result.solve_time_seconds)}</p>
                ) : null}
                {result.results.map((item) => (
                  <div key={item.id} className="rounded-[7px] border border-line bg-white p-3">
                    <div className="mb-2 flex items-center justify-between gap-3">
                      <span className="font-bold">{item.name || "Test case"}</span>
                      <StatusBadge status={item.status} />
                    </div>
                    {!item.is_hidden || item.is_sample ? (
                      <div className="grid gap-2 md:grid-cols-2">
                        <pre className="overflow-auto rounded-[7px] bg-[#fffaf0] p-2 text-xs">Output: {item.stdout || "(empty)"}</pre>
                        <pre className="overflow-auto rounded-[7px] bg-[#fffaf0] p-2 text-xs">Expected: {item.expected_output || "(empty)"}</pre>
                      </div>
                    ) : (
                      <p className="text-xs text-muted">Hidden test case</p>
                    )}
                    {item.stderr ? <pre className="mt-2 overflow-auto rounded-[7px] bg-orange-50 p-2 text-xs text-orange-800">{item.stderr}</pre> : null}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted">Run sample tests or submit against all tests.</p>
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

function timerStorageKey(slug: string) {
  return `crack-interviews:${slug}:timer`;
}

function readSavedTimer(slug: string, solveTimeSeconds: number | null, timerLocked: boolean) {
  if (timerLocked) {
    return {
      elapsedSeconds: solveTimeSeconds ?? 0,
      running: false,
      started: true,
    };
  }

  if (typeof window === "undefined") {
    return {
      elapsedSeconds: 0,
      running: false,
      started: false,
    };
  }

  try {
    const rawTimer = window.localStorage.getItem(timerStorageKey(slug));
    if (!rawTimer) {
      return {
        elapsedSeconds: 0,
        running: false,
        started: false,
      };
    }

    const savedTimer = JSON.parse(rawTimer) as Partial<SavedTimer>;
    if (typeof savedTimer.elapsedSeconds !== "number" || typeof savedTimer.running !== "boolean" || typeof savedTimer.updatedAt !== "string") {
      return {
        elapsedSeconds: 0,
        running: false,
        started: false,
      };
    }

    const elapsedSinceSave = savedTimer.running
      ? Math.max(0, Math.floor((Date.now() - new Date(savedTimer.updatedAt).getTime()) / 1000))
      : 0;

    return {
      elapsedSeconds: Math.max(0, Math.floor(savedTimer.elapsedSeconds + elapsedSinceSave)),
      running: savedTimer.running,
      started: true,
    };
  } catch {
    return {
      elapsedSeconds: 0,
      running: false,
      started: false,
    };
  }
}

function saveTimer(slug: string, timer: SavedTimer) {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(timerStorageKey(slug), JSON.stringify(timer));
}

function clearSavedTimer(slug: string) {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(timerStorageKey(slug));
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

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

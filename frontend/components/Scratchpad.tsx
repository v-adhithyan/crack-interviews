"use client";

import Editor from "@monaco-editor/react";
import { Play, RotateCcw } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { AppHeader } from "@/components/AppHeader";
import { getScratchpadDraft, runScratchpad, saveScratchpadDraft, type Language, type ScratchpadRunResult } from "@/lib/api";

const DEFAULTS: Record<Language, string> = {
  python: 'def solve():\n    print("Hello, world!")\n\nsolve()\n',
  java: 'public class Main {\n    public static void main(String[] args) {\n        System.out.println("Hello, world!");\n    }\n}\n',
};

export function Scratchpad() {
  const [language, setLanguage] = useState<Language>("python");
  const [code, setCode] = useState(DEFAULTS.python);
  const [javaCode, setJavaCode] = useState(DEFAULTS.java);
  const [pythonCode, setPythonCode] = useState(DEFAULTS.python);
  const [input, setInput] = useState("");
  const [result, setResult] = useState<ScratchpadRunResult | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [saveStatus, setSaveStatus] = useState("Loading draft…");
  const [loadError, setLoadError] = useState("");
  const initialized = useRef(false);
  const saveQueue = useRef<Promise<void>>(Promise.resolve());
  const codeRef = useRef(code);
  codeRef.current = code;

  useEffect(() => {
    let active = true;
    getScratchpadDraft().then((draft) => {
      if (!active) return;
      const nextJava = draft.java_code;
      const nextPython = draft.python_code;
      setJavaCode(nextJava);
      setPythonCode(nextPython);
      setLanguage(draft.selected_language);
      setCode(draft.selected_language === "java" ? nextJava : nextPython);
      initialized.current = true;
      setSaveStatus("Saved to your account");
    }).catch((error: unknown) => {
      if (active) {
        setLoadError(error instanceof Error ? error.message : "Could not load your draft.");
        initialized.current = true;
        setSaveStatus("Not saved");
      }
    });
    return () => { active = false; };
  }, []);

  const persist = useCallback(async (nextLanguage: Language, nextCode: string, nextJava: string, nextPython: string) => {
    if (!initialized.current) return;
    saveQueue.current = saveQueue.current.catch(() => undefined).then(async () => {
      setSaveStatus("Saving…");
      try {
        await saveScratchpadDraft({ selected_language: nextLanguage, java_code: nextJava, python_code: nextPython });
        setSaveStatus("Saved to your account");
      } catch {
        setSaveStatus("Save failed");
      }
    });
    await saveQueue.current;
  }, []);

  useEffect(() => {
    if (!initialized.current) return;
    const timer = window.setTimeout(() => { void persist(language, code, javaCode, pythonCode); }, 650);
    return () => window.clearTimeout(timer);
  }, [language, code, javaCode, pythonCode, persist]);

  function changeCode(value: string | undefined) {
    const next = value ?? "";
    setCode(next);
    if (language === "java") setJavaCode(next);
    else setPythonCode(next);
  }

  function changeLanguage(next: Language) {
    if (next === language) return;
    if (language === "java") setJavaCode(codeRef.current);
    else setPythonCode(codeRef.current);
    const nextCode = next === "java" ? javaCode : pythonCode;
    setLanguage(next);
    setCode(nextCode);
    setResult(null);
  }

  async function run() {
    setIsRunning(true);
    setResult(null);
    try {
      setResult(await runScratchpad(language, code, input));
    } catch (error) {
      setResult({ stdout: "", stderr: error instanceof Error ? error.message : "Unable to run code.", execution_time_ms: 0, status: "runtime_error" });
    } finally {
      setIsRunning(false);
    }
  }

  function resetCode() {
    changeCode(DEFAULTS[language]);
    setResult(null);
  }

  return (
    <main className="min-h-screen bg-paper text-ink">
      <AppHeader rightSlot={<Link href="/" className="rounded-[7px] border border-line bg-white px-3 py-2 text-sm font-bold">Questions</Link>} />
      <section className="mx-auto max-w-5xl px-3 py-4 sm:px-6 sm:py-8">
        <div className="mb-4 flex items-start justify-between gap-3">
          <div><p className="text-xs font-bold uppercase tracking-wide text-muted">Practice anywhere</p><h1 className="text-2xl font-[850]">Scratchpad</h1></div>
          <span className="pt-2 text-xs font-semibold text-muted" aria-live="polite">{saveStatus}</span>
        </div>
        {loadError ? <p className="mb-3 rounded-lg bg-orange-50 p-3 text-sm text-orange-800">Could not load the saved draft: {loadError}</p> : null}
        <section className="overflow-hidden rounded-xl border border-line bg-white shadow-product" aria-label="Code scratchpad">
          <div className="flex min-h-14 items-center justify-between gap-2 border-b border-line bg-[#fffaf0] px-3 py-2">
            <div className="flex rounded-lg border border-line bg-white p-1" role="group" aria-label="Programming language">
              {(["python", "java"] as const).map((item) => <button key={item} type="button" onClick={() => changeLanguage(item)} aria-pressed={language === item} className={`min-h-10 rounded-md px-4 text-sm font-bold ${language === item ? "bg-gold text-black" : "text-muted"}`}>{item === "python" ? "Python" : "Java"}</button>)}
            </div>
            <button type="button" onClick={resetCode} className="flex min-h-10 items-center gap-2 rounded-md px-3 text-sm font-bold text-muted hover:bg-white" aria-label="Reset code"><RotateCcw size={15} /><span className="hidden sm:inline">Reset</span></button>
          </div>
          <div className="h-[48vh] min-h-[300px] max-h-[620px] sm:h-[52vh]">
            <Editor height="100%" language={language} value={code} onChange={changeCode} theme="vs" options={{ automaticLayout: true, minimap: { enabled: false }, fontSize: 15, lineHeight: 24, wordWrap: "on", scrollBeyondLastLine: false, padding: { top: 12, bottom: 12 }, tabSize: 4, suggestOnTriggerCharacters: false, quickSuggestions: false, folding: false, glyphMargin: false, lineNumbersMinChars: 2, scrollbar: { verticalScrollbarSize: 8, horizontalScrollbarSize: 8 }, }} loading={<div className="p-4 text-sm text-muted">Loading editor…</div>} />
          </div>
          <div className="grid border-t border-line sm:grid-cols-2">
            <label className="grid border-b border-line sm:border-b-0 sm:border-r sm:border-line">
              <span className="px-3 pt-3 text-xs font-bold uppercase tracking-wide text-muted">Standard input</span>
              <textarea value={input} onChange={(event) => setInput(event.target.value)} placeholder="Optional input for your program" rows={4} className="min-h-24 resize-y bg-transparent px-3 py-2 font-mono text-sm outline-none placeholder:text-muted/70" />
            </label>
            <div className="min-h-32 p-3" aria-live="polite">
              <div className="mb-2 flex items-center justify-between gap-2"><span className="text-xs font-bold uppercase tracking-wide text-muted">Output</span>{result ? <span className={`text-xs font-bold ${result.status === "completed" ? "text-emerald-700" : "text-orange-700"}`}>{result.status.replaceAll("_", " ")} · {result.execution_time_ms} ms</span> : null}</div>
              {result ? <pre className="max-h-52 overflow-auto whitespace-pre-wrap break-words font-mono text-sm">{result.stdout}{result.stderr ? <span className="text-orange-700">{result.stdout ? "\n" : ""}{result.stderr}</span> : ""}</pre> : <p className="text-sm text-muted">Run your code to see its output here.</p>}
            </div>
          </div>
          <div className="sticky bottom-0 flex border-t border-line bg-white p-3 sm:static sm:justify-end">
            <button type="button" onClick={run} disabled={isRunning || !code.trim()} className="flex min-h-12 w-full items-center justify-center gap-2 rounded-lg bg-gradient-to-br from-[#ffd400] to-gold px-5 text-base font-[850] text-black disabled:opacity-60 sm:w-auto"><Play size={17} fill="currentColor" />{isRunning ? "Running…" : "Run code"}</button>
          </div>
        </section>
        <p className="mt-3 text-center text-xs text-muted">Your Java and Python drafts save automatically to your account.</p>
      </section>
    </main>
  );
}

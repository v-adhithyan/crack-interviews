"use client";

import Editor from "@monaco-editor/react";
import { Check, Clipboard, Play, X } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { AppHeader } from "@/components/AppHeader";
import { closeInterviewRoom, getInterviewRoom, runInterviewRoom, shareInterviewRoom, updateInterviewRoom, type InterviewRoom, type InterviewRunResult, type Language } from "@/lib/api";

const STARTERS: Record<Language, string> = {
  python: "def solve():\n    pass\n\n",
  java: "public class Main {\n    public static void main(String[] args) {\n        \n    }\n}\n",
};

export function InterviewRoomWorkspace({ roomId }: { roomId: string }) {
  const [room, setRoom] = useState<InterviewRoom | null>(null);
  const roomRef = useRef<InterviewRoom | null>(null);
  const dirtyRef = useRef(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [candidateName, setCandidateName] = useState("");
  const [candidateEmail, setCandidateEmail] = useState("");
  const [isJoining, setIsJoining] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [runResult, setRunResult] = useState<InterviewRunResult | null>(null);
  const [copyState, setCopyState] = useState<"idle" | "copied" | "failed">("idle");
  const [isClosing, setIsClosing] = useState(false);
  const [hrEmail, setHrEmail] = useState("");
  const [isSharing, setIsSharing] = useState(false);
  const [reviewLink, setReviewLink] = useState("");

  const receiveRoom = useCallback((next: InterviewRoom) => {
    roomRef.current = next;
    setRoom(next);
  }, []);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const loaded = await getInterviewRoom(roomId);
        if (active) {
          receiveRoom(loaded);
          setCandidateName(loaded.candidate_name);
          setCandidateEmail(loaded.candidate_email);
        }
      } catch (err) {
        if (active) setError(err instanceof Error ? err.message : "Unable to load this interview.");
      } finally {
        if (active) setIsLoading(false);
      }
    }
    void load();
    return () => { active = false; };
  }, [receiveRoom, roomId]);

  useEffect(() => {
    if (!room?.id || room.is_closed) return;
    const timer = window.setInterval(async () => {
      if (dirtyRef.current || roomRef.current?.is_closed) return;
      try {
        const latest = await getInterviewRoom(roomId);
        if (!dirtyRef.current) receiveRoom(latest);
      } catch (err) {
        if (roomRef.current?.role === "candidate" && err instanceof Error && err.message === "This interview has ended and is no longer available.") {
          roomRef.current = null;
          setRoom(null);
          setError(err.message);
          return;
        }
        // Keep the current workspace available through short network interruptions.
      }
    }, 1200);
    return () => window.clearInterval(timer);
  }, [receiveRoom, room?.id, room?.is_closed, roomId]);

  useEffect(() => {
    if (!room || !dirtyRef.current || room.is_closed) return;
    const snapshot = room;
    const timer = window.setTimeout(async () => {
      setIsSaving(true);
      try {
        const payload = snapshot.role === "interviewer"
          ? { title: snapshot.title, problem_statement: snapshot.problem_statement, language: snapshot.language, code: snapshot.code, stdin: snapshot.stdin }
          : { language: snapshot.language, code: snapshot.code, stdin: snapshot.stdin };
        const saved = await updateInterviewRoom(roomId, payload);
        const current = roomRef.current;
        const stillSame = current && current.title === snapshot.title && current.problem_statement === snapshot.problem_statement && current.language === snapshot.language && current.code === snapshot.code && current.stdin === snapshot.stdin;
        if (stillSame) {
          dirtyRef.current = false;
          receiveRoom(saved);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to sync changes.");
      } finally {
        setIsSaving(false);
      }
    }, 450);
    return () => window.clearTimeout(timer);
  }, [receiveRoom, room, roomId]);

  function updateLocal(changes: Partial<InterviewRoom>) {
    dirtyRef.current = true;
    setRoom((current) => {
      if (!current) return current;
      const next = { ...current, ...changes };
      roomRef.current = next;
      return next;
    });
    setError("");
  }

  async function joinRoom(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsJoining(true);
    setError("");
    try {
      const joined = await updateInterviewRoom(roomId, { candidate_name: candidateName, candidate_email: candidateEmail });
      dirtyRef.current = false;
      receiveRoom(joined);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to join this interview.");
    } finally {
      setIsJoining(false);
    }
  }

  async function copyInvite() {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopyState("copied");
    } catch {
      setCopyState("failed");
    }
    window.setTimeout(() => setCopyState("idle"), 2200);
  }

  async function runCode() {
    if (!room) return;
    setIsRunning(true);
    setRunResult(null);
    setError("");
    try {
      const snapshot = roomRef.current ?? room;
      const payload = snapshot.role === "interviewer"
        ? { title: snapshot.title, problem_statement: snapshot.problem_statement, language: snapshot.language, code: snapshot.code, stdin: snapshot.stdin }
        : { language: snapshot.language, code: snapshot.code, stdin: snapshot.stdin };
      const saved = await updateInterviewRoom(roomId, payload);
      dirtyRef.current = false;
      receiveRoom(saved);
      setRunResult(await runInterviewRoom(roomId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to run this code.");
    } finally {
      setIsRunning(false);
    }
  }

  async function endInterview() {
    if (!window.confirm("End this interview? The candidate link will lose access to the problem and code.")) return;
    setIsClosing(true);
    try {
      dirtyRef.current = false;
      receiveRoom(await closeInterviewRoom(roomId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to end the interview.");
    } finally {
      setIsClosing(false);
    }
  }

  async function shareWithHr(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSharing(true);
    setError("");
    try {
      const updated = await shareInterviewRoom(roomId, hrEmail);
      receiveRoom(updated);
      setHrEmail("");
      const reviewUrl = new URL(`/interview/${roomId}/review`, window.location.origin).toString();
      setReviewLink(reviewUrl);
      try {
        await navigator.clipboard.writeText(reviewUrl);
        setCopyState("copied");
      } catch {
        setCopyState("failed");
      }
      window.setTimeout(() => setCopyState("idle"), 2200);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to share this interview with HR.");
    } finally {
      setIsSharing(false);
    }
  }

  async function copyReviewLink() {
    try {
      await navigator.clipboard.writeText(reviewLink);
      setCopyState("copied");
    } catch {
      setCopyState("failed");
    }
    window.setTimeout(() => setCopyState("idle"), 2200);
  }

  if (isLoading) return <main className="grid min-h-screen place-items-center bg-paper text-sm font-bold text-muted">Loading interview room…</main>;
  if (!room) return <main className="min-h-screen bg-paper p-6 text-center"><p className="rounded-lg bg-orange-50 p-4 text-sm font-semibold text-orange-800">{error || "Interview room not found."}</p><Link href="/" className="mt-4 inline-block text-sm font-bold underline">Back to HackerLeap</Link></main>;

  const isInterviewer = room.role === "interviewer";
  const isCandidateUnjoined = room.role === "candidate" && (!room.candidate_joined || !room.candidate_email);
  const canEdit = !room.is_closed && !isCandidateUnjoined;

  if (isCandidateUnjoined) {
    return (
      <main className="min-h-screen bg-paper text-ink">
        <AppHeader />
        <section className="mx-auto max-w-md px-4 py-12 sm:py-20">
          <p className="mb-2 text-sm font-bold text-muted">You were invited to an interview</p>
          <h1 className="text-2xl font-[850]">{room.title}</h1>
          <p className="mt-2 text-sm text-muted">Hosted by {room.interviewer_name}. You can join without creating an account. Your email will be shared with the interviewer for follow-up.</p>
          {room.is_closed ? <p className="mt-5 rounded-lg bg-orange-50 p-4 text-sm font-semibold text-orange-800">This interview room is closed.</p> : (
            <form className="mt-6 grid gap-4 rounded-xl border border-line bg-white p-5 shadow-product" onSubmit={joinRoom}>
              <label className="grid gap-2 text-sm font-bold">Your name<input value={candidateName} onChange={(event) => setCandidateName(event.target.value)} required maxLength={100} autoComplete="name" className="h-12 rounded-lg border border-line px-3 text-base font-medium outline-none focus:border-gold" placeholder="Name shown to the interviewer" /></label>
              <label className="grid gap-2 text-sm font-bold">Email address<input type="email" value={candidateEmail} onChange={(event) => setCandidateEmail(event.target.value)} required maxLength={254} autoComplete="email" className="h-12 rounded-lg border border-line px-3 text-base font-medium outline-none focus:border-gold" placeholder="you@example.com" /></label>
              {error ? <p role="alert" className="rounded-lg bg-orange-50 p-3 text-sm text-orange-800">{error}</p> : null}
              <button disabled={isJoining} className="min-h-12 rounded-lg bg-gradient-to-br from-[#ffd400] to-gold px-4 font-[850] text-black disabled:opacity-60">{isJoining ? "Joining…" : "Join interview"}</button>
            </form>
          )}
        </section>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-paper text-ink">
      <AppHeader rightSlot={<><span className="hidden text-xs font-bold text-muted sm:inline">{isInterviewer ? "Interviewer" : room.role === "reviewer" ? "HR reviewer" : "Candidate"}</span><Link href="/" className="rounded-md border border-line bg-white px-3 py-2 text-xs font-bold">Exit</Link></>} />
      <section className="mx-auto max-w-[1440px] px-3 py-3 sm:px-5 sm:py-5">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0"><p className="text-xs font-bold uppercase tracking-wide text-muted">{isInterviewer ? "Interview room" : `Interview with ${room.interviewer_name}`}</p><h1 className="truncate text-xl font-[850] sm:text-2xl">{room.title}</h1></div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold text-muted" aria-live="polite">{room.is_closed ? "Ended" : isSaving ? "Syncing…" : room.candidate_joined ? `With ${room.candidate_name}` : "Waiting for candidate"}</span>
            {isInterviewer && !room.is_closed ? <button type="button" onClick={copyInvite} className="inline-flex min-h-10 items-center gap-2 rounded-md border border-line bg-white px-3 text-sm font-bold"><Clipboard size={15} />{copyState === "copied" ? "Link copied" : "Copy invite link"}</button> : null}
            {isInterviewer && !room.is_closed ? <button type="button" onClick={endInterview} disabled={isClosing} className="inline-flex min-h-10 items-center gap-2 rounded-md border border-line bg-white px-3 text-sm font-bold text-muted"><X size={15} />End</button> : null}
          </div>
        </div>
        {error ? <p role="alert" className="mb-3 rounded-lg bg-orange-50 p-3 text-sm font-semibold text-orange-800">{error}</p> : null}
        {room.is_closed ? <p className="mb-3 rounded-lg border border-line bg-white p-3 text-sm font-semibold text-muted">This room has ended. Only you and the HR reviewers you add can access the problem and code.</p> : null}
        {isInterviewer && room.is_closed ? <section className="mb-3 rounded-xl border border-line bg-white p-4 shadow-product"><h2 className="text-sm font-bold">Share interview review with HR</h2><p className="mt-1 text-xs leading-5 text-muted">Add an HR account email, then share the review link. They must sign in with that same email.</p><form className="mt-3 flex flex-col gap-2 sm:flex-row" onSubmit={shareWithHr}><input type="email" value={hrEmail} onChange={(event) => setHrEmail(event.target.value)} required maxLength={254} placeholder="hr@company.com" aria-label="HR email address" className="h-10 min-w-0 flex-1 rounded-md border border-line px-3 text-sm outline-none focus:border-gold" /><button type="submit" disabled={isSharing} className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md bg-gradient-to-br from-[#ffd400] to-gold px-3 text-sm font-bold text-black disabled:opacity-60"><Clipboard size={14} />{isSharing ? "Sharing…" : copyState === "copied" ? "Review link copied" : "Grant access & copy link"}</button></form>{reviewLink ? <div className="mt-3 flex flex-col gap-2 sm:flex-row"><input aria-label="HR review link" readOnly value={reviewLink} onFocus={(event) => event.currentTarget.select()} className="h-10 min-w-0 flex-1 rounded-md border border-line bg-paper px-3 text-xs text-muted" /><button type="button" onClick={copyReviewLink} className="min-h-10 rounded-md border border-line px-3 text-sm font-bold">{copyState === "copied" ? "Link copied" : copyState === "failed" ? "Select link to copy" : "Copy review link"}</button></div> : null}{room.hr_share_emails?.length ? <div className="mt-3 flex flex-wrap gap-2">{room.hr_share_emails.map((email) => <span key={email} className="rounded-full bg-[#fffaf0] px-3 py-1 text-xs font-semibold text-muted">{email}</span>)}</div> : null}</section> : null}
        <div className="grid gap-3 lg:min-h-[calc(100vh-155px)] lg:grid-cols-[minmax(280px,0.8fr)_minmax(0,1.4fr)]">
          <section className="flex min-h-56 flex-col overflow-hidden rounded-xl border border-line bg-white shadow-product lg:min-h-0">
            <h2 className="border-b border-line bg-[#fffaf0] px-4 py-3 text-sm font-bold">Problem</h2>
            {isInterviewer && canEdit ? <div className="grid gap-2 p-3"><input aria-label="Interview title" value={room.title} onChange={(event) => updateLocal({ title: event.target.value })} maxLength={160} className="h-10 rounded-md border border-line px-2 text-sm font-bold outline-none focus:border-gold" /><textarea aria-label="Problem statement" value={room.problem_statement} onChange={(event) => updateLocal({ problem_statement: event.target.value })} maxLength={12000} placeholder="Add the problem statement or interview prompt" className="min-h-44 flex-1 resize-y rounded-md border border-line p-2 text-sm leading-6 outline-none focus:border-gold lg:min-h-0" /></div>
              : <div className="min-h-44 flex-1 whitespace-pre-wrap p-4 text-sm leading-6 text-ink">{room.problem_statement || <span className="text-muted">The interviewer has not added a problem statement yet.</span>}</div>}
          </section>
          <section className="flex min-h-[590px] flex-col overflow-hidden rounded-xl border border-line bg-white shadow-product lg:min-h-0">
            <div className="flex min-h-14 items-center justify-between gap-2 border-b border-line bg-[#fffaf0] px-3 py-2">
              <div className="flex rounded-lg border border-line bg-white p-1" role="group" aria-label="Programming language">{(["python", "java"] as const).map((language) => <button key={language} type="button" disabled={!canEdit} aria-pressed={room.language === language} onClick={() => updateLocal({ language, code: room.code || STARTERS[language] })} className={`min-h-9 rounded-md px-3 text-xs font-bold disabled:opacity-60 sm:px-4 sm:text-sm ${room.language === language ? "bg-gold text-black" : "text-muted"}`}>{language === "python" ? "Python 3" : "Java 17"}</button>)}</div>
              <button type="button" onClick={runCode} disabled={!canEdit || isRunning || !room.code.trim()} className="inline-flex min-h-10 items-center gap-2 rounded-md bg-gradient-to-br from-[#ffd400] to-gold px-3 text-sm font-[850] text-black disabled:opacity-50 sm:px-4"><Play size={15} fill="currentColor" />{isRunning ? "Running…" : "Run"}</button>
            </div>
            <div className="h-[44vh] min-h-[280px] flex-1 bg-[#10151f] lg:h-auto lg:min-h-0">
              <Editor height="100%" language={room.language} value={room.code} onChange={(value) => updateLocal({ code: value ?? "" })} theme="vs-dark" options={{ readOnly: !canEdit, automaticLayout: true, minimap: { enabled: false }, fontSize: 14, lineHeight: 22, wordWrap: "on", scrollBeyondLastLine: false, tabSize: 4, padding: { top: 12, bottom: 12 }, scrollbar: { verticalScrollbarSize: 8, horizontalScrollbarSize: 8 } }} loading={<div className="p-4 text-sm text-white/60">Loading editor…</div>} />
            </div>
            <div className="grid border-t border-line sm:grid-cols-2">
              <label className="grid border-b border-line sm:border-b-0 sm:border-r"><span className="px-3 pt-2 text-[11px] font-bold uppercase tracking-wide text-muted">Standard input</span><textarea value={room.stdin} readOnly={!canEdit} onChange={(event) => updateLocal({ stdin: event.target.value })} rows={3} placeholder="Optional input" className="min-h-20 resize-y px-3 py-2 font-mono text-sm outline-none placeholder:text-muted/70" /></label>
              <div className="min-h-24 p-3" aria-live="polite"><div className="mb-2 flex items-center justify-between"><span className="text-[11px] font-bold uppercase tracking-wide text-muted">Output</span>{runResult ? <span className={`text-[11px] font-bold ${runResult.status === "completed" ? "text-emerald-700" : "text-orange-700"}`}>{runResult.status.replaceAll("_", " ")} · {runResult.execution_time_ms} ms</span> : null}</div>{runResult ? <pre className="max-h-44 overflow-auto whitespace-pre-wrap break-words font-mono text-sm">{runResult.stdout}{runResult.stderr ? <span className="text-orange-700">{runResult.stdout ? "\n" : ""}{runResult.stderr}</span> : ""}</pre> : <p className="text-xs text-muted">Run the shared code to see output here.</p>}</div>
            </div>
            <div className="flex items-center justify-between gap-3 border-t border-line px-3 py-2 text-[11px] text-muted"><span>Changes sync automatically</span>{room.candidate_joined ? <span className="inline-flex min-w-0 items-center gap-1 truncate"><Check size={12} className="shrink-0" />{room.candidate_name}{isInterviewer && room.candidate_email ? <span className="truncate">· {room.candidate_email}</span> : null}</span> : <span>Share the link to invite your candidate</span>}</div>
          </section>
        </div>
      </section>
    </main>
  );
}

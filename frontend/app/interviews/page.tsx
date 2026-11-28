"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { AppHeader } from "@/components/AppHeader";
import { AuthGate } from "@/components/AuthGate";
import { createInterviewRoom, type Language } from "@/lib/api";

export default function InterviewsPage() {
  return <AuthGate>{(user) => <CreateInterviewPage email={user.email} />}</AuthGate>;
}

function CreateInterviewPage({ email }: { email: string }) {
  const router = useRouter();
  const [title, setTitle] = useState("Problem solving interview");
  const [problemStatement, setProblemStatement] = useState("");
  const [language, setLanguage] = useState<Language>("python");
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState("");

  async function createRoom(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsCreating(true);
    setError("");
    try {
      const room = await createInterviewRoom({ title, problem_statement: problemStatement, language });
      router.push(`/interview/${room.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create the interview room.");
    } finally {
      setIsCreating(false);
    }
  }

  return (
    <main className="min-h-screen bg-paper text-ink">
      <AppHeader rightSlot={<span className="hidden max-w-44 truncate text-xs font-semibold text-muted sm:block">{email}</span>} />
      <section className="mx-auto max-w-3xl px-4 py-7 sm:px-6 sm:py-12">
        <p className="mb-2 text-sm font-bold text-muted">Live problem solving</p>
        <h1 className="text-3xl font-[850]">Host an interview</h1>
        <p className="mb-7 mt-2 max-w-xl text-sm leading-6 text-muted">Create a private room, share its link with your candidate, and work through a problem together.</p>
        <form className="grid gap-5 rounded-xl border border-line bg-white p-4 shadow-product sm:p-6" onSubmit={createRoom}>
          <label className="grid gap-2 text-sm font-bold">
            Interview title
            <input value={title} onChange={(event) => setTitle(event.target.value)} maxLength={160} required className="h-12 rounded-lg border border-line px-3 text-base font-medium outline-none focus:border-gold focus:ring-2 focus:ring-gold/20" />
          </label>
          <label className="grid gap-2 text-sm font-bold">
            Problem statement <span className="font-normal text-muted">(optional; you can edit it in the room too)</span>
            <textarea value={problemStatement} onChange={(event) => setProblemStatement(event.target.value)} maxLength={12000} rows={7} placeholder="Paste or write the problem for your candidate" className="resize-y rounded-lg border border-line px-3 py-3 text-sm font-medium leading-6 outline-none focus:border-gold focus:ring-2 focus:ring-gold/20" />
          </label>
          <label className="grid max-w-xs gap-2 text-sm font-bold">
            Starting language
            <select value={language} onChange={(event) => setLanguage(event.target.value as Language)} className="h-12 rounded-lg border border-line bg-white px-3 text-base outline-none focus:border-gold">
              <option value="python">Python 3</option><option value="java">Java 17</option>
            </select>
          </label>
          {error ? <p role="alert" className="rounded-lg bg-orange-50 p-3 text-sm font-semibold text-orange-800">{error}</p> : null}
          <button disabled={isCreating} className="min-h-12 rounded-lg bg-gradient-to-br from-[#ffd400] to-gold px-5 text-base font-[850] text-black disabled:opacity-60" type="submit">{isCreating ? "Creating room…" : "Create interview room"}</button>
          <p className="text-xs leading-5 text-muted">Interview rooms can only be hosted from a corporate email account. Candidates join from your private link without an account.</p>
        </form>
      </section>
    </main>
  );
}

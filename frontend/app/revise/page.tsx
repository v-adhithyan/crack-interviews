"use client";

import { ArrowLeft, BookOpen } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { AppHeader } from "@/components/AppHeader";
import { AuthGate } from "@/components/AuthGate";
import { AutoHeightCodeBlock } from "@/components/AutoHeightCodeBlock";
import { getRevisionSubmissions, type RevisionSubmission } from "@/lib/api";
import { usePageTitle } from "@/lib/usePageTitle";

export default function RevisePage() {
  return (
    <AuthGate>
      {() => <ReviseContent />}
    </AuthGate>
  );
}

function ReviseContent() {
  const [items, setItems] = useState<RevisionSubmission[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  usePageTitle("Revise");

  useEffect(() => {
    async function loadRevisionItems() {
      try {
        setItems(await getRevisionSubmissions());
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to load revision list.");
      } finally {
        setIsLoading(false);
      }
    }
    loadRevisionItems();
  }, []);

  if (isLoading) {
    return <main className="grid min-h-screen place-items-center bg-paper text-sm font-bold text-muted">Loading revision list...</main>;
  }

  return (
    <main className="min-h-screen bg-paper text-ink">
      <AppHeader
        rightSlot={
          <Link href="/" className="inline-flex h-10 items-center gap-2 rounded-[7px] border border-line bg-white px-3 text-sm font-bold hover:bg-[#fffaf0]">
            <ArrowLeft size={16} />
            Questions
          </Link>
        }
      />

      <section className="mx-auto max-w-6xl px-6 py-8">
        <div className="mb-5">
          <p className="text-sm font-bold text-muted">Quick review before interview</p>
          <h1 className="text-2xl font-[850]">Revise</h1>
        </div>

        {error ? <div className="rounded-lg border border-orange-200 bg-orange-50 p-4 text-sm font-bold text-orange-700">{error}</div> : null}

        {!error && items.length === 0 ? (
          <div className="rounded-lg border border-[rgba(15,23,42,0.08)] bg-white/90 p-8 text-center shadow-product">
            <BookOpen className="mx-auto mb-3 text-muted" size={28} />
            <h2 className="text-lg font-[850]">No revision items yet</h2>
            <p className="mt-2 text-sm text-muted">Solve a problem, then mark it for revision from the question page.</p>
          </div>
        ) : null}

        <div className="grid gap-6">
          {items.map((item, index) => (
            <article key={item.id} className="overflow-hidden rounded-lg border border-[rgba(15,23,42,0.08)] bg-white/90 shadow-product">
              <div className="flex items-start justify-between gap-4 border-b border-line bg-[#fffaf0] px-4 py-3">
                <div>
                  <p className="text-xs font-bold uppercase tracking-normal text-muted">Question {index + 1}</p>
                  <h2 className="text-lg font-[850]">{item.question_title}</h2>
                </div>
                <Link href={`/questions/${item.question_slug}`} className="shrink-0 text-sm font-bold text-muted hover:text-[#d08a00]">
                  Open problem
                </Link>
              </div>
              <div className="px-4 py-3 text-xs font-bold uppercase tracking-normal text-muted">
                {item.language === "java" ? "Java 17" : "Python 3"} solution
              </div>
              <div className="px-4 pb-4">
                <AutoHeightCodeBlock code={item.code} language={item.language} />
              </div>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}

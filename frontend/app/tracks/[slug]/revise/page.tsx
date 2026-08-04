"use client";

import { ArrowLeft, BookOpen, CheckCircle2 } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { AppHeader } from "@/components/AppHeader";
import { AuthGate } from "@/components/AuthGate";
import { AutoHeightCodeBlock } from "@/components/AutoHeightCodeBlock";
import { getTrackRevisionSubmissions, type RevisionSubmission } from "@/lib/api";
import { INTERVIEW_PREPARATION_TRACK, withTrackContext, type TrackContext } from "@/lib/trackContext";
import { usePageTitle } from "@/lib/usePageTitle";

export default function TrackRevisePage({ params }: { params: { slug: string } }) {
  return <AuthGate>{() => <TrackReviseContent slug={params.slug} />}</AuthGate>;
}

function TrackReviseContent({ slug }: { slug: string }) {
  const [items, setItems] = useState<RevisionSubmission[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  usePageTitle("Interview Preparation Revision");

  useEffect(() => {
    async function loadItems() {
      try {
        setItems(await getTrackRevisionSubmissions(slug));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to load solved interview questions.");
      } finally {
        setIsLoading(false);
      }
    }
    loadItems();
  }, [slug]);

  if (isLoading) {
    return <main className="grid min-h-screen place-items-center bg-paper text-sm font-bold text-muted">Loading solved questions...</main>;
  }

  const trackContext: TrackContext | null = slug === INTERVIEW_PREPARATION_TRACK ? { slug: INTERVIEW_PREPARATION_TRACK, tag: null } : null;

  return (
    <main className="min-h-screen bg-paper text-ink">
      <AppHeader
        centerSlot={<span className="text-sm font-bold text-muted">{items.length} solved</span>}
        rightSlot={
          <Link href={`/tracks/${slug}`} className="inline-flex h-10 items-center gap-2 rounded-[7px] border border-line bg-white px-3 text-sm font-bold hover:bg-[#fffaf0]">
            <ArrowLeft size={16} />
            Back to track
          </Link>
        }
      />

      <section className="mx-auto max-w-6xl px-6 py-8">
        <div className="mb-6">
          <p className="text-sm font-bold text-muted">Automatically includes every solved problem</p>
          <h1 className="text-2xl font-[850]">Interview Preparation Revision</h1>
          <p className="mt-2 max-w-3xl text-sm font-semibold leading-6 text-muted">
            Your latest accepted solution for each solved Interview Preparation problem appears here automatically. This list is separate from manually marked revision questions.
          </p>
        </div>

        {error ? <div className="rounded-lg border border-orange-200 bg-orange-50 p-4 text-sm font-bold text-orange-700">{error}</div> : null}

        {!error && items.length === 0 ? (
          <div className="rounded-lg border border-[rgba(15,23,42,0.08)] bg-white/90 p-8 text-center shadow-product">
            <BookOpen className="mx-auto mb-3 text-muted" size={28} />
            <h2 className="text-lg font-[850]">No solved track problems yet</h2>
            <p className="mt-2 text-sm text-muted">Submit an accepted solution in the Interview Preparation track and it will appear here automatically.</p>
          </div>
        ) : null}

        <div className="grid gap-6">
          {items.map((item, index) => (
            <article key={item.id} className="overflow-hidden rounded-lg border border-[rgba(15,23,42,0.08)] bg-white/90 shadow-product">
              <div className="flex items-start justify-between gap-4 border-b border-line bg-[#fffaf0] px-4 py-3">
                <div>
                  <p className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-normal text-emerald-700">
                    <CheckCircle2 size={14} />
                    Solved problem {index + 1}
                  </p>
                  <h2 className="mt-1 text-lg font-[850]">{item.question_title}</h2>
                </div>
                <Link href={withTrackContext(`/questions/${item.question_slug}`, trackContext)} className="shrink-0 text-sm font-bold text-muted hover:text-[#d08a00]">
                  Solve again
                </Link>
              </div>
              <div className="px-4 py-3 text-xs font-bold uppercase tracking-normal text-muted">
                Latest accepted {item.language === "java" ? "Java 17" : "Python 3"} solution
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

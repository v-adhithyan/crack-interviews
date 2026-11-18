"use client";

import { ArrowLeft, BookOpen, CheckCircle2, ListFilter } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { AppHeader } from "@/components/AppHeader";
import { AuthGate } from "@/components/AuthGate";
import { RevisionSolutionCard } from "@/components/RevisionSolutionCard";
import { getTrack, getTrackRevisionSubmissions } from "@/lib/api";
import { INTERVIEW_PREPARATION_TRACK, normalizedTag, trackReturnPath, withTrackContext, type TrackContext } from "@/lib/trackContext";
import { addRevisionTags, filterRevisionByTag, getRevisionTagOptions, type TrackRevisionSubmission } from "@/lib/trackRevision";
import { usePageTitle } from "@/lib/usePageTitle";

export default function TrackRevisePage({ params }: { params: { slug: string } }) {
  return <AuthGate>{() => <TrackReviseContent slug={params.slug} />}</AuthGate>;
}

function TrackReviseContent({ slug }: { slug: string }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [items, setItems] = useState<TrackRevisionSubmission[]>([]);
  const [selectedTag, setSelectedTag] = useState(() => normalizedTag(searchParams.get("tag")) ?? "all");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  usePageTitle("Interview Preparation Revision");

  useEffect(() => {
    async function loadItems() {
      try {
        const [submissions, track] = await Promise.all([getTrackRevisionSubmissions(slug), getTrack(slug)]);
        setItems(addRevisionTags(submissions, track.sections));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to load solved interview questions.");
      } finally {
        setIsLoading(false);
      }
    }
    loadItems();
  }, [slug]);

  useEffect(() => {
    setSelectedTag(normalizedTag(searchParams.get("tag")) ?? "all");
  }, [searchParams]);

  const availableTags = useMemo(() => getRevisionTagOptions(items), [items]);
  const filteredItems = useMemo(() => filterRevisionByTag(items, selectedTag), [items, selectedTag]);

  if (isLoading) {
    return <main className="grid min-h-screen place-items-center bg-paper text-sm font-bold text-muted">Loading solved questions...</main>;
  }

  const trackContext: TrackContext | null = slug === INTERVIEW_PREPARATION_TRACK
    ? { slug: INTERVIEW_PREPARATION_TRACK, tag: selectedTag === "all" ? null : selectedTag }
    : null;

  function updateSelectedTag(tag: string) {
    setSelectedTag(tag);
    const params = new URLSearchParams(searchParams.toString());
    if (tag === "all") {
      params.delete("tag");
    } else {
      params.set("tag", tag);
    }
    const query = params.toString();
    router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
  }

  return (
    <main className="min-h-screen bg-paper text-ink">
      <AppHeader
        centerSlot={<span className="text-sm font-bold text-muted">{filteredItems.length}/{items.length} solved</span>}
        rightSlot={
          <Link href={trackContext ? trackReturnPath(trackContext) : `/tracks/${slug}`} className="inline-flex h-10 items-center gap-2 rounded-[7px] border border-line bg-white px-3 text-sm font-bold hover:bg-[#fffaf0]">
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

        {!error && items.length > 0 ? (
          <div className="mb-5 flex flex-wrap items-center gap-3">
            <label className="inline-flex h-10 items-center gap-2 rounded-[7px] border border-line bg-white px-3 text-sm font-bold shadow-product">
              <ListFilter size={15} />
              <select value={selectedTag} onChange={(event) => updateSelectedTag(event.target.value)} className="bg-transparent outline-none" aria-label="Filter revision solutions by tag">
                <option value="all">All tags</option>
                {availableTags.map(([tagSlug, name]) => (
                  <option key={tagSlug} value={tagSlug}>{name}</option>
                ))}
              </select>
            </label>
            <span className="text-sm font-bold text-muted">
              Showing {filteredItems.length} of {items.length} solved problems
            </span>
          </div>
        ) : null}

        {!error && items.length === 0 ? (
          <div className="rounded-lg border border-[rgba(15,23,42,0.08)] bg-white/90 p-8 text-center shadow-product">
            <BookOpen className="mx-auto mb-3 text-muted" size={28} />
            <h2 className="text-lg font-[850]">No solved track problems yet</h2>
            <p className="mt-2 text-sm text-muted">Submit an accepted solution in the Interview Preparation track and it will appear here automatically.</p>
          </div>
        ) : null}

        {!error && items.length > 0 && filteredItems.length === 0 ? (
          <div className="rounded-lg border border-[rgba(15,23,42,0.08)] bg-white/90 p-8 text-center shadow-product">
            <ListFilter className="mx-auto mb-3 text-muted" size={28} />
            <h2 className="text-lg font-[850]">No solved problems match this tag</h2>
            <button type="button" onClick={() => updateSelectedTag("all")} className="mt-3 text-sm font-bold text-[#b77900] hover:text-[#8a5b00]">Show all solved problems</button>
          </div>
        ) : null}

        <div className="grid gap-6">
          {filteredItems.map((item, index) => (
            <RevisionSolutionCard
              key={item.id}
              submission={item}
              href={withTrackContext(`/questions/${item.question_slug}`, trackContext)}
              linkLabel="Solve again"
              solutionPrefix="Latest accepted "
              heading={
                <>
                  <p className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-normal text-emerald-700">
                    <CheckCircle2 size={14} />
                    Solved problem {index + 1}
                  </p>
                  <h2 className="mt-1 text-lg font-[850]">{item.question_title}</h2>
                  <span className="mt-2 flex flex-wrap gap-1">
                    {item.tags.map((tag) => (
                      <span key={tag.slug} className="rounded-[6px] bg-[#eef6ff] px-2 py-1 text-[11px] font-bold text-[#175cd3]">{tag.name}</span>
                    ))}
                  </span>
                </>
              }
            />
          ))}
        </div>
      </section>
    </main>
  );
}

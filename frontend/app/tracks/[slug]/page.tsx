"use client";

import { ArrowLeft, BookOpen, CheckCircle2, Circle, Clock, ListFilter } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import type { MouseEvent } from "react";
import { useEffect, useMemo, useState } from "react";
import { AppHeader } from "@/components/AppHeader";
import { AuthGate } from "@/components/AuthGate";
import { getTrack, type TrackDetail } from "@/lib/api";
import { INTERVIEW_PREPARATION_TRACK, normalizedTag, withTrackContext } from "@/lib/trackContext";
import { usePageTitle } from "@/lib/usePageTitle";

const difficultyStyles = {
  easy: "bg-mint text-emerald-800",
  medium: "bg-soft text-[#946200]",
  hard: "bg-orange-100 text-orange-700",
};

export default function TrackPage({ params }: { params: { slug: string } }) {
  return <AuthGate>{() => <TrackDetailPage slug={params.slug} />}</AuthGate>;
}

function TrackDetailPage({ slug }: { slug: string }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [track, setTrack] = useState<TrackDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedTag, setSelectedTag] = useState(() => normalizedTag(searchParams.get("tag")) ?? "all");
  const [openingSlug, setOpeningSlug] = useState("");
  usePageTitle(track?.title ?? "Track");

  useEffect(() => {
    async function loadTrack() {
      try {
        setTrack(await getTrack(slug));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to load track.");
      } finally {
        setIsLoading(false);
      }
    }
    loadTrack();
  }, [slug]);

  useEffect(() => {
    setSelectedTag(normalizedTag(searchParams.get("tag")) ?? "all");
  }, [searchParams]);

  const questions = useMemo(() => track?.sections.flatMap((section) => section.questions) ?? [], [track]);
  const solvedCount = questions.filter((question) => question.solved).length;
  const totalCount = questions.length;
  const availableTags = useMemo(() => {
    const tags = new Map<string, string>();
    questions.forEach((question) => question.tags?.forEach((tag) => tags.set(tag.slug, tag.name)));
    return Array.from(tags.entries()).sort((left, right) => left[1].localeCompare(right[1]));
  }, [questions]);

  const filteredSections = useMemo(() => {
    if (!track) {
      return [];
    }
    return track.sections
      .map((section) => ({
        ...section,
        questions: selectedTag === "all" ? section.questions : section.questions.filter((question) => question.tags?.some((tag) => tag.slug === selectedTag)),
      }))
      .filter((section) => section.questions.length > 0);
  }, [selectedTag, track]);

  function handleQuestionClick(event: MouseEvent<HTMLAnchorElement>, questionSlug: string) {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
      return;
    }
    setOpeningSlug(questionSlug);
  }

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
      {openingSlug ? (
        <div className="fixed inset-0 z-40 grid place-items-center bg-white/55 px-6 backdrop-blur-[2px]" role="status" aria-live="polite">
          <div className="rounded-lg border border-line bg-white px-5 py-4 text-sm font-bold text-muted shadow-product">Loading question...</div>
        </div>
      ) : null}
      <AppHeader
        centerSlot={
          <div className="hidden text-sm font-bold text-muted sm:block">
            {totalCount ? `${solvedCount}/${totalCount} solved` : "Interview Preparation"}
          </div>
        }
        rightSlot={
          <>
            {slug === INTERVIEW_PREPARATION_TRACK ? (
              <Link
                href={`/tracks/${slug}/revise`}
                aria-label="Revise solved interview questions"
                title="Revise solved interview questions"
                className="inline-flex h-10 items-center gap-2 rounded-[7px] border border-line bg-white px-3 text-sm font-bold hover:bg-[#fffaf0]"
              >
                <BookOpen size={16} />
                <span className="hidden sm:inline">Revise solved</span>
              </Link>
            ) : null}
            <Link
              href="/"
              aria-label="Back to questions"
              title="Back to questions"
              className="grid h-10 w-10 shrink-0 place-items-center rounded-[7px] border border-line bg-white text-sm font-bold hover:bg-[#fffaf0]"
            >
              <ArrowLeft size={16} />
            </Link>
          </>
        }
      />

      <section className="mx-auto max-w-6xl px-6 py-8">
        {isLoading ? (
          <div className="rounded-lg border border-line bg-white px-4 py-10 text-center text-muted shadow-product">Loading track...</div>
        ) : error ? (
          <div className="rounded-lg border border-line bg-white px-4 py-10 text-center font-bold text-orange-700 shadow-product">{error}</div>
        ) : track ? (
          <>
            <div className="mb-6 grid gap-4 md:grid-cols-[1fr_240px] md:items-end">
              <div>
                <p className="text-sm font-bold text-muted">Structured path</p>
                <h1 className="text-2xl font-[850]">{track.title}</h1>
                {track.description ? <p className="mt-2 max-w-3xl text-sm font-semibold leading-6 text-muted">{track.description}</p> : null}
              </div>
              <div className="rounded-lg border border-line bg-white px-4 py-3 shadow-product">
                <div className="mb-2 flex items-center justify-between text-sm font-bold">
                  <span>Progress</span>
                  <span>{totalCount ? Math.round((solvedCount / totalCount) * 100) : 0}%</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-[#edf2f7]">
                  <div className="h-full rounded-full bg-gold" style={{ width: `${totalCount ? (solvedCount / totalCount) * 100 : 0}%` }} />
                </div>
              </div>
            </div>

            <div className="mb-5 flex flex-wrap items-center gap-3">
              <label className="inline-flex h-10 items-center gap-2 rounded-[7px] border border-line bg-white px-3 text-sm font-bold">
                <ListFilter size={15} />
                <select value={selectedTag} onChange={(event) => updateSelectedTag(event.target.value)} className="bg-transparent outline-none" aria-label="Filter track by tag">
                  <option value="all">All tags</option>
                  {availableTags.map(([tagSlug, name]) => (
                    <option key={tagSlug} value={tagSlug}>
                      {name}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <div className="space-y-6">
              {filteredSections.map((section) => {
                const sectionSolved = section.questions.filter((question) => question.solved).length;
                return (
                  <section key={section.id} className="overflow-hidden rounded-lg border border-line bg-white shadow-product">
                    <div className="border-b border-line bg-[#fffaf0] px-4 py-4">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <h2 className="text-lg font-[850]">{section.title}</h2>
                          {section.description ? <p className="mt-1 text-sm font-semibold leading-6 text-muted">{section.description}</p> : null}
                        </div>
                        <span className="rounded-[7px] border border-line bg-white px-3 py-2 text-sm font-bold text-muted">
                          {sectionSolved}/{section.questions.length}
                        </span>
                      </div>
                    </div>
                    <div>
                      {section.questions.map((question) => (
                        <Link
                          key={question.id}
                          href={withTrackContext(
                            `/questions/${question.slug}`,
                            slug === INTERVIEW_PREPARATION_TRACK
                              ? { slug: INTERVIEW_PREPARATION_TRACK, tag: normalizedTag(selectedTag) }
                              : null,
                          )}
                          onClick={(event) => handleQuestionClick(event, question.slug)}
                          className="grid gap-2 border-b border-line px-4 py-4 transition last:border-0 hover:bg-[#fffaf0] md:grid-cols-[1fr_170px_130px_120px] md:items-center md:gap-0"
                        >
                          <span className="flex min-w-0 items-center gap-3">
                            {question.solved ? <CheckCircle2 className="shrink-0 text-green-600" size={18} /> : <Circle className="shrink-0 text-muted/60" size={18} />}
                            <span className="min-w-0">
                              <span className="block truncate text-[15px] font-semibold text-ink">{question.title}</span>
                              {question.pattern_note ? <span className="block text-xs font-bold text-muted">{question.pattern_note}</span> : null}
                            </span>
                          </span>
                          <span className="flex flex-wrap gap-1">
                            {(question.tags ?? []).slice(0, 2).map((tag) => (
                              <span key={tag.slug} className="rounded-[6px] bg-[#eef6ff] px-2 py-1 text-[11px] font-bold text-[#175cd3]">
                                {tag.name}
                              </span>
                            ))}
                          </span>
                          <span>
                            <span className={`inline-flex h-7 items-center rounded-[7px] px-2 text-xs font-bold ${difficultyStyles[question.difficulty]}`}>
                              {question.difficulty}
                            </span>
                          </span>
                          <span className="inline-flex items-center gap-1 text-sm font-bold text-muted">
                            <Clock size={14} />
                            {question.recommended_time_minutes} min
                          </span>
                        </Link>
                      ))}
                    </div>
                  </section>
                );
              })}
            </div>
          </>
        ) : null}
      </section>
    </main>
  );
}

"use client";

import { ArrowDown, ArrowUp, ArrowUpDown, BookOpen, CheckCircle2, Circle, GraduationCap, Search } from "lucide-react";
import Link from "next/link";
import type { MouseEvent } from "react";
import { useEffect, useMemo, useState } from "react";
import { AppHeader } from "@/components/AppHeader";
import { AuthGate } from "@/components/AuthGate";
import { getQuestions, type QuestionListItem } from "@/lib/api";
import { usePageTitle } from "@/lib/usePageTitle";

const difficultyStyles = {
  easy: "bg-mint text-emerald-800",
  medium: "bg-soft text-[#946200]",
  hard: "bg-orange-100 text-orange-700",
};

type SortKey = "title" | "difficulty" | "tests" | "status";
type SortDirection = "asc" | "desc";

const difficultyRank: Record<QuestionListItem["difficulty"], number> = {
  easy: 1,
  medium: 2,
  hard: 3,
};

export default function HomePage() {
  return (
    <AuthGate>
      {() => <QuestionListPage />}
    </AuthGate>
  );
}

function QuestionListPage() {
  const [questions, setQuestions] = useState<QuestionListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedTag, setSelectedTag] = useState("all");
  const [visibleCount, setVisibleCount] = useState(100);
  const [sortKey, setSortKey] = useState<SortKey>("title");
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");
  const [openingSlug, setOpeningSlug] = useState("");
  usePageTitle("Questions");

  useEffect(() => {
    async function loadQuestions() {
      try {
        setQuestions(await getQuestions());
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to load questions.");
      } finally {
        setIsLoading(false);
      }
    }
    loadQuestions();
  }, []);

  const availableTags = useMemo(() => {
    const tags = new Map<string, string>();
    questions.forEach((question) => {
      question.tags?.forEach((tag) => tags.set(tag.slug, tag.name));
    });
    return Array.from(tags.entries()).sort((left, right) => left[1].localeCompare(right[1]));
  }, [questions]);

  const filteredQuestions = useMemo(() => {
    const normalizedSearch = searchTerm.trim().toLowerCase();
    return questions.filter((question) => {
      const tagSlugs = question.tags?.map((tag) => tag.slug) ?? [];
      const tagNames = question.tags?.map((tag) => tag.name.toLowerCase()) ?? [];
      const matchesTag = selectedTag === "all" || tagSlugs.includes(selectedTag);
      if (!matchesTag) {
        return false;
      }
      if (!normalizedSearch) {
        return true;
      }
      return (
        question.title.toLowerCase().includes(normalizedSearch) ||
        question.difficulty.includes(normalizedSearch) ||
        tagSlugs.some((tag) => tag.includes(normalizedSearch)) ||
        tagNames.some((tag) => tag.includes(normalizedSearch))
      );
    });
  }, [questions, searchTerm, selectedTag]);

  const sortedQuestions = useMemo(() => {
    return [...filteredQuestions].sort((left, right) => {
      const direction = sortDirection === "asc" ? 1 : -1;
      if (sortKey === "title") {
        return left.title.localeCompare(right.title) * direction;
      }
      if (sortKey === "difficulty") {
        return (difficultyRank[left.difficulty] - difficultyRank[right.difficulty]) * direction;
      }
      if (sortKey === "tests") {
        return (left.test_case_count - right.test_case_count) * direction;
      }
      return (Number(left.solved) - Number(right.solved)) * direction;
    });
  }, [filteredQuestions, sortDirection, sortKey]);

  const visibleQuestions = sortedQuestions.slice(0, visibleCount);

  useEffect(() => {
    setVisibleCount(100);
  }, [searchTerm, selectedTag, sortKey, sortDirection]);

  useEffect(() => {
    function handleScroll() {
      const remaining = document.documentElement.scrollHeight - window.scrollY - window.innerHeight;
      if (remaining < 480) {
        setVisibleCount((current) => Math.min(current + 100, sortedQuestions.length));
      }
    }

    window.addEventListener("scroll", handleScroll, { passive: true });
    handleScroll();
    return () => window.removeEventListener("scroll", handleScroll);
  }, [sortedQuestions.length]);

  function updateSort(nextKey: SortKey) {
    if (nextKey === sortKey) {
      setSortDirection((current) => (current === "asc" ? "desc" : "asc"));
      return;
    }
    setSortKey(nextKey);
    setSortDirection("asc");
  }

  function handleQuestionClick(event: MouseEvent<HTMLAnchorElement>, slug: string) {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
      return;
    }
    setOpeningSlug(slug);
  }

  return (
    <main className="min-h-screen bg-paper text-ink">
      {openingSlug ? (
        <div className="fixed inset-0 z-40 grid place-items-center bg-white/55 px-6 backdrop-blur-[2px]" role="status" aria-live="polite">
          <div className="rounded-lg border border-line bg-white px-5 py-4 text-sm font-bold text-muted shadow-product">Loading question...</div>
        </div>
      ) : null}
      <AppHeader
        rightSlot={
          <>
            <Link
              href="/tracks/interview-preparation"
              aria-label="Interview preparation"
              title="Interview preparation"
              className="grid h-10 w-10 shrink-0 place-items-center rounded-[7px] border border-line bg-white text-sm font-bold hover:bg-[#fffaf0]"
            >
              <GraduationCap size={16} />
            </Link>
            <Link
              href="/revise"
              aria-label="Revise"
              title="Revise"
              className="grid h-10 w-10 shrink-0 place-items-center rounded-[7px] border border-line bg-white text-sm font-bold hover:bg-[#fffaf0]"
            >
              <BookOpen size={16} />
            </Link>
            <div className="rounded border border-[rgba(247,184,1,0.45)] bg-white px-3 py-2 text-sm font-[850] text-muted">
              {questions.filter((question) => question.solved).length}/{questions.length} solved
            </div>
          </>
        }
      />

      <section className="mx-auto max-w-6xl px-6 py-8">
        <div className="mb-5">
          <p className="text-sm font-bold text-muted">Let's crack the coding interview.</p>
          <h1 className="text-2xl font-[850]">Questions</h1>
        </div>
        <div className="mb-4 grid gap-3 md:grid-cols-[1fr_220px]">
          <label className="relative block">
            <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" size={16} />
            <input
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
              placeholder="Search questions, tags, or difficulty"
              className="h-11 w-full rounded-[7px] border border-line bg-white px-9 text-sm font-semibold outline-none transition focus:border-gold focus:ring-2 focus:ring-gold/20"
            />
          </label>
          <select
            value={selectedTag}
            onChange={(event) => setSelectedTag(event.target.value)}
            className="h-11 w-full rounded-[7px] border border-line bg-white px-3 text-sm font-bold text-ink outline-none transition focus:border-gold focus:ring-2 focus:ring-gold/20"
            aria-label="Filter by tag"
          >
            <option value="all">All tags</option>
            {availableTags.map(([slug, name]) => (
              <option key={slug} value={slug}>
                {name}
              </option>
            ))}
          </select>
        </div>
        <div className="overflow-hidden rounded-lg border border-[rgba(15,23,42,0.08)] bg-white/90 shadow-product">
          <div className="hidden grid-cols-[1fr_180px_120px_100px_120px] border-b border-line bg-[#fffaf0] px-4 py-3 text-xs font-bold uppercase tracking-normal text-muted md:grid">
            <SortHeader label="Question" sortKey="title" activeKey={sortKey} direction={sortDirection} onSort={updateSort} />
            <span>Tags</span>
            <SortHeader label="Difficulty" sortKey="difficulty" activeKey={sortKey} direction={sortDirection} onSort={updateSort} />
            <SortHeader label="Tests" sortKey="tests" activeKey={sortKey} direction={sortDirection} onSort={updateSort} />
            <SortHeader label="Status" sortKey="status" activeKey={sortKey} direction={sortDirection} onSort={updateSort} />
          </div>
          {isLoading ? (
            <div className="px-4 py-10 text-center text-muted">Loading questions...</div>
          ) : error ? (
            <div className="px-4 py-10 text-center font-bold text-orange-700">{error}</div>
          ) : questions.length === 0 ? (
            <div className="px-4 py-10 text-center text-muted">No active questions yet. Add one in Django admin.</div>
          ) : sortedQuestions.length === 0 ? (
            <div className="px-4 py-10 text-center text-muted">No questions match your filters.</div>
          ) : (
            visibleQuestions.map((question) => (
              <Link
                key={question.id}
                href={`/questions/${question.slug}`}
                onClick={(event) => handleQuestionClick(event, question.slug)}
                className="grid gap-2 border-b border-line px-4 py-4 transition last:border-0 hover:bg-[#fffaf0] md:grid-cols-[1fr_180px_120px_100px_120px] md:items-center md:gap-0"
              >
                <span className="text-[15px] font-semibold text-ink">{question.title}</span>
                <span className="flex min-w-0 flex-wrap gap-1">
                  {(question.tags ?? []).slice(0, 2).map((tag) => (
                    <span key={tag.slug} className="inline-flex max-w-full items-center rounded-[6px] bg-[#eef6ff] px-2 py-1 text-[11px] font-bold text-[#175cd3]">
                      {tag.name}
                    </span>
                  ))}
                  {(question.tags?.length ?? 0) > 2 ? <span className="text-xs font-bold text-muted">+{(question.tags?.length ?? 0) - 2}</span> : null}
                </span>
                <span>
                  <span className={`inline-flex h-7 items-center rounded-[7px] px-2 text-xs font-bold ${difficultyStyles[question.difficulty]}`}>
                    {question.difficulty}
                  </span>
                </span>
                <span className="text-sm text-muted">{question.test_case_count}</span>
                <span className="inline-flex items-center gap-2 text-sm font-bold">
                  {question.solved ? <CheckCircle2 className="text-green-600" size={18} /> : <Circle className="text-muted/60" size={18} />}
                  {question.solved ? "Solved" : "Unsolved"}
                </span>
              </Link>
            ))
          )}
        </div>
        {!isLoading && sortedQuestions.length > visibleQuestions.length ? (
          <div className="py-5 text-center text-sm font-bold text-muted">Showing {visibleQuestions.length} of {sortedQuestions.length}</div>
        ) : null}
      </section>
    </main>
  );
}

function SortHeader({
  label,
  sortKey,
  activeKey,
  direction,
  onSort,
}: {
  label: string;
  sortKey: SortKey;
  activeKey: SortKey;
  direction: SortDirection;
  onSort: (sortKey: SortKey) => void;
}) {
  const isActive = sortKey === activeKey;
  const Icon = isActive ? (direction === "asc" ? ArrowUp : ArrowDown) : ArrowUpDown;

  return (
    <button
      type="button"
      onClick={() => onSort(sortKey)}
      className="inline-flex w-fit items-center gap-1 rounded-[6px] text-left uppercase tracking-normal transition hover:text-ink focus:outline-none focus:ring-2 focus:ring-gold/45"
      aria-label={`Sort by ${label} ${isActive && direction === "asc" ? "descending" : "ascending"}`}
      title={`Sort by ${label}`}
    >
      <span>{label}</span>
      <Icon size={13} aria-hidden="true" />
    </button>
  );
}

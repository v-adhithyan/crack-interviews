"use client";

import { ArrowDown, ArrowUp, ArrowUpDown, BookOpen, CheckCircle2, Circle } from "lucide-react";
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

  const sortedQuestions = useMemo(() => {
    return [...questions].sort((left, right) => {
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
  }, [questions, sortDirection, sortKey]);

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
        <div className="overflow-hidden rounded-lg border border-[rgba(15,23,42,0.08)] bg-white/90 shadow-product">
          <div className="grid grid-cols-[1fr_120px_110px_120px] border-b border-line bg-[#fffaf0] px-4 py-3 text-xs font-bold uppercase tracking-normal text-muted">
            <SortHeader label="Question" sortKey="title" activeKey={sortKey} direction={sortDirection} onSort={updateSort} />
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
          ) : (
            sortedQuestions.map((question) => (
              <Link
                key={question.id}
                href={`/questions/${question.slug}`}
                onClick={(event) => handleQuestionClick(event, question.slug)}
                className="grid grid-cols-[1fr_120px_110px_120px] items-center border-b border-line px-4 py-4 transition last:border-0 hover:bg-[#fffaf0]"
              >
                <span className="text-[15px] font-semibold text-ink">{question.title}</span>
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

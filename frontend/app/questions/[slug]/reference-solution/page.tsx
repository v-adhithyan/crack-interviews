"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AppHeader } from "@/components/AppHeader";
import { AuthGate } from "@/components/AuthGate";
import { SubmittedCodeViewer } from "@/components/SubmittedCodeViewer";
import { getQuestionReferenceSolution, type Language, type QuestionReferenceSolution } from "@/lib/api";
import { usePageTitle } from "@/lib/usePageTitle";
import { TrackReturnOverlay } from "@/components/TrackReturnOverlay";
import { getTrackContext, withTrackContext } from "@/lib/trackContext";

export default function ReferenceSolutionPage({ params }: { params: { slug: string } }) {
  return (
    <AuthGate>
      {(user) => <ReferenceSolutionContent slug={params.slug} isStaff={user.is_staff} />}
    </AuthGate>
  );
}

function ReferenceSolutionContent({ slug, isStaff }: { slug: string; isStaff: boolean }) {
  const searchParams = useSearchParams();
  const trackSlug = getTrackContext(searchParams);
  const [solution, setSolution] = useState<QuestionReferenceSolution | null>(null);
  const [language, setLanguage] = useState<Language>("java");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  usePageTitle(solution ? `${solution.title} reference solution` : isLoading ? "Loading reference solution" : "Reference solution");

  useEffect(() => {
    async function loadSolution() {
      try {
        const loadedSolution = await getQuestionReferenceSolution(slug);
        setSolution(loadedSolution);
        setLanguage(loadedSolution.java_reference_solution.trim() ? "java" : "python");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to load reference solution.");
      } finally {
        setIsLoading(false);
      }
    }
    loadSolution();
  }, [slug]);

  const availableLanguages = useMemo(() => {
    if (!solution) {
      return [];
    }
    return (["java", "python"] as const).filter((option) => codeForLanguage(solution, option).trim());
  }, [solution]);

  if (isLoading) {
    return <main className="grid min-h-screen place-items-center bg-paper text-sm font-bold text-muted">Loading reference solution...</main>;
  }

  if (!isStaff) {
    return <main className="grid min-h-screen place-items-center bg-paper px-6 text-center font-bold text-orange-700">Admin access is required.</main>;
  }

  if (error || !solution) {
    return <main className="grid min-h-screen place-items-center bg-paper px-6 text-center font-bold text-orange-700">{error || "Reference solution not found."}</main>;
  }

  return (
    <main className="min-h-screen bg-paper text-ink">
      <TrackReturnOverlay trackSlug={trackSlug} />
      <AppHeader
        rightSlot={
          <div className="inline-flex rounded-[7px] border border-line bg-white p-0.5">
            {availableLanguages.map((option) => (
              <button
                key={option}
                type="button"
                onClick={() => setLanguage(option)}
                disabled={language === option}
                className={`h-9 rounded-[6px] px-3 text-xs font-bold transition disabled:cursor-default ${
                  language === option ? "bg-soft text-ink" : "text-muted hover:bg-[#fffaf0] hover:text-ink"
                }`}
              >
                {option === "java" ? "Java 17" : "Python 3"}
              </button>
            ))}
          </div>
        }
      />

      <section className="mx-auto max-w-6xl px-6 py-8">
        <div className="mb-5">
          <Link href={withTrackContext(`/questions/${solution.slug}`, trackSlug)} className="mb-2 inline-flex items-center gap-2 text-sm font-bold text-muted hover:text-[#d08a00]">
            <ArrowLeft size={16} />
            Back to question
          </Link>
          <p className="text-sm font-bold text-muted">Admin reference solution</p>
          <h1 className="text-2xl font-[850]">{solution.title}</h1>
        </div>
        <div className="rounded-lg border border-[rgba(15,23,42,0.08)] bg-white/90 p-4 shadow-product">
          <h2 className="mb-3 text-sm font-bold uppercase tracking-normal text-muted">
            {language === "java" ? "Java 17" : "Python 3"} reference solution
          </h2>
          <SubmittedCodeViewer code={codeForLanguage(solution, language)} language={language} />
        </div>
      </section>
    </main>
  );
}

function codeForLanguage(solution: QuestionReferenceSolution, language: Language) {
  return language === "java" ? solution.java_reference_solution : solution.python_reference_solution;
}

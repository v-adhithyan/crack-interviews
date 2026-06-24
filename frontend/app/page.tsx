import { CheckCircle2, Circle, Code2 } from "lucide-react";
import Link from "next/link";
import { getQuestions } from "@/lib/api";

const difficultyStyles = {
  easy: "bg-mint text-emerald-800",
  medium: "bg-soft text-[#946200]",
  hard: "bg-orange-100 text-orange-700",
};

export default async function HomePage() {
  const questions = await getQuestions();

  return (
    <main className="min-h-screen bg-paper text-ink">
      <header className="border-b border-line bg-white/75">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
          <div className="flex items-center gap-3">
            <div className="grid size-10 place-items-center rounded-[10px] bg-gradient-to-br from-[#ffe66b] to-gold-strong text-ink shadow-[inset_8px_0_0_rgba(247,184,1,0.52)]">
              <Code2 size={20} strokeWidth={2.8} />
            </div>
            <div>
              <h1 className="text-xl font-[850]">HackerLeap</h1>
              <p className="text-sm text-muted">Let's crack the coding interview.</p>
            </div>
          </div>
          <div className="rounded border border-[rgba(247,184,1,0.45)] bg-white px-3 py-2 text-sm font-[850] text-muted">
            {questions.filter((question) => question.solved).length}/{questions.length} solved
          </div>
        </div>
      </header>

      <section className="mx-auto max-w-6xl px-6 py-8">
        <div className="overflow-hidden rounded-lg border border-[rgba(15,23,42,0.08)] bg-white/90 shadow-product">
          <div className="grid grid-cols-[1fr_120px_110px_120px] border-b border-line bg-[#fffaf0] px-4 py-3 text-xs font-bold uppercase tracking-normal text-muted">
            <span>Question</span>
            <span>Difficulty</span>
            <span>Tests</span>
            <span>Status</span>
          </div>
          {questions.length === 0 ? (
            <div className="px-4 py-10 text-center text-muted">No active questions yet. Add one in Django admin.</div>
          ) : (
            questions.map((question) => (
              <Link
                key={question.id}
                href={`/questions/${question.slug}`}
                className="grid grid-cols-[1fr_120px_110px_120px] items-center border-b border-line px-4 py-4 transition last:border-0 hover:bg-[#fffaf0]"
              >
                <span className="font-[850]">{question.title}</span>
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

import { CheckCircle2, Circle, Code2 } from "lucide-react";
import Link from "next/link";
import { getQuestions } from "@/lib/api";

const difficultyStyles = {
  easy: "bg-emerald-100 text-emerald-800",
  medium: "bg-amber-100 text-amber-900",
  hard: "bg-rose-100 text-rose-800",
};

export default async function HomePage() {
  const questions = await getQuestions();

  return (
    <main className="min-h-screen bg-paper">
      <header className="border-b border-line bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
          <div className="flex items-center gap-3">
            <div className="grid size-10 place-items-center rounded bg-ink text-white">
              <Code2 size={20} />
            </div>
            <div>
              <h1 className="text-xl font-bold">Crack Interviews</h1>
              <p className="text-sm text-zinc-600">Python practice, one problem at a time.</p>
            </div>
          </div>
          <div className="text-sm font-semibold text-zinc-600">
            {questions.filter((question) => question.solved).length}/{questions.length} solved
          </div>
        </div>
      </header>

      <section className="mx-auto max-w-6xl px-6 py-8">
        <div className="overflow-hidden rounded border border-line bg-white">
          <div className="grid grid-cols-[1fr_120px_110px_120px] border-b border-line bg-zinc-50 px-4 py-3 text-xs font-bold uppercase tracking-normal text-zinc-500">
            <span>Question</span>
            <span>Difficulty</span>
            <span>Tests</span>
            <span>Status</span>
          </div>
          {questions.length === 0 ? (
            <div className="px-4 py-10 text-center text-zinc-600">No active questions yet. Add one in Django admin.</div>
          ) : (
            questions.map((question) => (
              <Link
                key={question.id}
                href={`/questions/${question.slug}`}
                className="grid grid-cols-[1fr_120px_110px_120px] items-center border-b border-line px-4 py-4 transition last:border-0 hover:bg-zinc-50"
              >
                <span className="font-semibold">{question.title}</span>
                <span>
                  <span className={`inline-flex h-7 items-center rounded px-2 text-xs font-semibold ${difficultyStyles[question.difficulty]}`}>
                    {question.difficulty}
                  </span>
                </span>
                <span className="text-sm text-zinc-600">{question.test_case_count}</span>
                <span className="inline-flex items-center gap-2 text-sm font-semibold">
                  {question.solved ? <CheckCircle2 className="text-emerald-600" size={18} /> : <Circle className="text-zinc-400" size={18} />}
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

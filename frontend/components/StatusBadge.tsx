import type { SubmissionStatus } from "@/lib/api";

const statusStyles: Record<SubmissionStatus, string> = {
  pending: "bg-zinc-200 text-zinc-700",
  accepted: "bg-emerald-100 text-emerald-800",
  wrong_answer: "bg-amber-100 text-amber-900",
  runtime_error: "bg-rose-100 text-rose-800",
  time_limit_exceeded: "bg-violet-100 text-violet-800",
};

const labels: Record<SubmissionStatus, string> = {
  pending: "Pending",
  accepted: "Accepted",
  wrong_answer: "Wrong answer",
  runtime_error: "Runtime error",
  time_limit_exceeded: "Time limit",
};

export function StatusBadge({ status }: { status: SubmissionStatus }) {
  return (
    <span className={`inline-flex h-7 items-center rounded px-2 text-xs font-semibold ${statusStyles[status]}`}>
      {labels[status]}
    </span>
  );
}

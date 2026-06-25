import type { SubmissionStatus } from "@/lib/api";

const statusStyles: Record<SubmissionStatus, string> = {
  pending: "bg-zinc-100 text-muted",
  accepted: "bg-mint text-emerald-800",
  wrong_answer: "bg-soft text-[#946200]",
  runtime_error: "bg-orange-100 text-orange-700",
  time_limit_exceeded: "bg-zinc-200 text-ink",
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
    <span className={`inline-flex h-7 w-fit max-w-full items-center justify-self-start rounded-[7px] px-2 text-xs font-bold ${statusStyles[status]}`}>
      {labels[status]}
    </span>
  );
}

import { ArrowLeft, ListChecks } from "lucide-react";
import Link from "next/link";
import { INTERVIEW_PREPARATION_TRACK } from "@/lib/trackContext";

type Props = {
  trackSlug?: string | null;
};

export function TrackReturnOverlay({ trackSlug }: Props) {
  if (trackSlug !== INTERVIEW_PREPARATION_TRACK) {
    return null;
  }

  return (
    <Link
      href={`/tracks/${INTERVIEW_PREPARATION_TRACK}`}
      aria-label="Back to Interview Preparation track"
      className="group fixed bottom-5 right-5 z-40 flex max-w-[calc(100vw-2.5rem)] items-center gap-3 rounded-lg border border-[rgba(247,184,1,0.55)] bg-white/95 px-3 py-2.5 shadow-product backdrop-blur transition hover:-translate-y-0.5 hover:bg-[#fffaf0] focus:outline-none focus:ring-2 focus:ring-gold"
    >
      <span className="grid h-9 w-9 shrink-0 place-items-center rounded-[7px] bg-soft text-[#946200]">
        <ArrowLeft size={17} />
      </span>
      <span className="min-w-0">
        <span className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wide text-[#946200]">
          <ListChecks size={13} />
          Current track
        </span>
        <span className="block truncate text-sm font-[850] text-ink">Back to Interview Preparation</span>
      </span>
    </Link>
  );
}

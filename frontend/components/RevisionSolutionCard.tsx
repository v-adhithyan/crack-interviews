import Link from "next/link";
import type { ReactNode } from "react";
import { AutoHeightCodeBlock } from "@/components/AutoHeightCodeBlock";
import type { RevisionSubmission } from "@/lib/api";

type Props = {
  submission: RevisionSubmission;
  heading: ReactNode;
  href: string;
  linkLabel: string;
  solutionPrefix?: string;
};

export function RevisionSolutionCard({ submission, heading, href, linkLabel, solutionPrefix = "" }: Props) {
  const languageLabel = submission.language === "java" ? "Java 17" : "Python 3";

  return (
    <article className="overflow-hidden rounded-lg border border-[rgba(15,23,42,0.08)] bg-white/90 shadow-product">
      <div className="flex items-start justify-between gap-4 border-b border-line bg-[#fffaf0] px-4 py-3">
        <div>{heading}</div>
        <Link href={href} className="shrink-0 text-sm font-bold text-muted hover:text-[#d08a00]">
          {linkLabel}
        </Link>
      </div>
      <div className="px-4 py-3 text-xs font-bold uppercase tracking-normal text-muted">
        {solutionPrefix}{languageLabel} solution
      </div>
      <div className="px-4 pb-4">
        <AutoHeightCodeBlock code={submission.code} language={submission.language} />
      </div>
    </article>
  );
}

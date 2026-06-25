import Link from "next/link";
import type { ReactNode } from "react";
import { BrandMark } from "@/components/BrandMark";

type AppHeaderProps = {
  centerSlot?: ReactNode;
  rightSlot?: ReactNode;
};

export function AppHeader({ centerSlot, rightSlot }: AppHeaderProps) {
  return (
    <header className="grid min-h-16 grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3 border-b border-line bg-white/75 px-4">
      <Link href="/" className="inline-flex shrink-0 items-center gap-3 font-[850] text-ink">
        <BrandMark size="sm" />
        <span>HackerLeap</span>
      </Link>
      <div className="flex min-w-0 items-center justify-center gap-2 overflow-hidden whitespace-nowrap">{centerSlot}</div>
      <div className="flex min-w-0 max-w-[62vw] items-center justify-end gap-2 overflow-x-auto whitespace-nowrap">{rightSlot}</div>
    </header>
  );
}

import Link from "next/link";
import type { ReactNode } from "react";
import { BrandMark } from "@/components/BrandMark";

type AppHeaderProps = {
  centerSlot?: ReactNode;
  rightSlot?: ReactNode;
};

export function AppHeader({ centerSlot, rightSlot }: AppHeaderProps) {
  return (
    <header className="grid min-h-16 grid-cols-[1fr_auto_1fr] items-center border-b border-line bg-white/75 px-4">
      <Link href="/" className="inline-flex items-center gap-3 font-[850] text-ink">
        <BrandMark size="sm" />
        <span>HackerLeap</span>
      </Link>
      <div className="flex items-center justify-center gap-2">{centerSlot}</div>
      <div className="flex items-center justify-end gap-2">{rightSlot}</div>
    </header>
  );
}

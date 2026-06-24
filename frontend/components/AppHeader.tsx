import Link from "next/link";
import type { ReactNode } from "react";
import { BrandMark } from "@/components/BrandMark";

type AppHeaderProps = {
  children?: ReactNode;
  rightSlot?: ReactNode;
  maxWidthClassName?: string;
};

export function AppHeader({ children, rightSlot, maxWidthClassName = "max-w-6xl" }: AppHeaderProps) {
  return (
    <header className="border-b border-line bg-white/75">
      <div className={`mx-auto flex ${maxWidthClassName} items-center justify-between gap-6 px-6 py-5`}>
        <div className="min-w-0">
          <Link href="/" className={`${children ? "mb-4" : ""} flex w-fit items-center gap-3 font-[850] text-ink`}>
            <BrandMark />
            <span className="text-xl">HackerLeap</span>
          </Link>
          {children}
        </div>
        {rightSlot ? <div className="shrink-0">{rightSlot}</div> : null}
      </div>
    </header>
  );
}

type BrandMarkProps = {
  size?: "sm" | "md" | "lg";
};

const sizeClasses = {
  sm: "size-9 text-sm",
  md: "size-10 text-sm",
  lg: "size-11 text-base",
};

export function BrandMark({ size = "md" }: BrandMarkProps) {
  return (
    <span className={`grid shrink-0 place-items-center rounded-[10px] bg-gradient-to-br from-[#ffe66b] to-gold-strong font-black text-ink shadow-[inset_8px_0_0_rgba(247,184,1,0.52)] ${sizeClasses[size]}`}>
      HL
    </span>
  );
}

import type { Language } from "@/lib/api";

type Props = {
  code: string;
  language: Language;
};

const KEYWORDS = new Set([
  "abstract",
  "boolean",
  "break",
  "case",
  "catch",
  "class",
  "continue",
  "def",
  "else",
  "extends",
  "false",
  "final",
  "finally",
  "for",
  "if",
  "import",
  "in",
  "int",
  "long",
  "new",
  "null",
  "private",
  "public",
  "return",
  "static",
  "string",
  "true",
  "try",
  "void",
  "while",
]);

export function AutoHeightCodeBlock({ code, language }: Props) {
  return (
    <pre className="overflow-x-auto rounded-[7px] border border-line bg-[#10151f] p-4 text-sm leading-6 text-[#d9dee7]">
      <code>
        {code.split("\n").map((line, index) => (
          <span key={`${index}-${line}`} className="block min-h-6">
            <span className="mr-4 inline-block w-8 select-none text-right text-[#6b7280]">{index + 1}</span>
            {highlightLine(line, language)}
          </span>
        ))}
      </code>
    </pre>
  );
}

function highlightLine(line: string, language: Language) {
  const commentStart = language === "python" ? line.indexOf("#") : line.indexOf("//");
  const codePart = commentStart >= 0 ? line.slice(0, commentStart) : line;
  const commentPart = commentStart >= 0 ? line.slice(commentStart) : "";

  return (
    <>
      {tokenize(codePart).map((part, index) => (
        <span key={`${index}-${part.value}`} className={part.className}>
          {part.value}
        </span>
      ))}
      {commentPart ? <span className="text-[#7da36c]">{commentPart}</span> : null}
    </>
  );
}

function tokenize(line: string) {
  const parts = line.split(/(\b[A-Za-z_][A-Za-z0-9_]*\b|"[^"]*"|'[^']*'|\b\d+\b)/g);
  return parts.filter(Boolean).map((value) => {
    const lowered = value.toLowerCase();
    if (KEYWORDS.has(lowered)) {
      return { value, className: "text-[#61afef]" };
    }
    if (/^["']/.test(value)) {
      return { value, className: "text-[#98c379]" };
    }
    if (/^\d+$/.test(value)) {
      return { value, className: "text-[#d19a66]" };
    }
    return { value, className: "" };
  });
}

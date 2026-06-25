"use client";

import Editor from "@monaco-editor/react";
import type { Language } from "@/lib/api";

type Props = {
  code: string;
  language: Language;
  className?: string;
};

export function SubmittedCodeViewer({ code, language, className = "h-[720px] max-h-[70vh] min-h-[360px]" }: Props) {
  return (
    <div className={`${className} w-full min-w-0 overflow-hidden rounded-[7px] border border-line bg-[#10151f]`}>
      <Editor
        height="100%"
        language={language === "java" ? "java" : "python"}
        theme="vs-dark"
        value={code}
        options={{
          automaticLayout: true,
          domReadOnly: true,
          fontSize: 14,
          lineNumbers: "on",
          minimap: { enabled: false },
          readOnly: true,
          renderLineHighlight: "none",
          scrollBeyondLastLine: false,
          tabSize: 4,
        }}
      />
    </div>
  );
}

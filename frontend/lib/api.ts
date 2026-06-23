const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api";

export type Language = "java" | "python";

export type QuestionListItem = {
  id: number;
  title: string;
  slug: string;
  difficulty: "easy" | "medium" | "hard";
  solved: boolean;
  test_case_count: number;
};

export type QuestionDetail = QuestionListItem & {
  description: string;
  starter_code: string;
  java_starter_code: string;
  python_starter_code: string;
  execution_mode: "stdin" | "function";
  function_name: string;
};

export type TestCaseResult = {
  id: number;
  name: string;
  is_sample: boolean;
  is_hidden: boolean;
  status: SubmissionStatus;
  stdout: string;
  stderr: string;
  expected_output: string;
  execution_time_ms: number;
};

export type SubmissionStatus = "pending" | "accepted" | "wrong_answer" | "runtime_error" | "time_limit_exceeded";

export type Submission = {
  id: number;
  question: number;
  question_slug: string;
  question_title: string;
  kind: "run" | "submit";
  language: Language;
  code: string;
  status: SubmissionStatus;
  stdout: string;
  stderr: string;
  execution_time_ms: number;
  solve_time_seconds: number | null;
  passed_count: number;
  total_count: number;
  created_at: string;
  results: TestCaseResult[];
};

export type SubmissionListItem = Omit<Submission, "code" | "stdout" | "stderr" | "results" | "question">;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail.detail ?? `Request failed with ${response.status}`);
  }

  return response.json();
}

export function getQuestions() {
  return request<QuestionListItem[]>("/questions/");
}

export function getQuestion(slug: string) {
  return request<QuestionDetail>(`/questions/${slug}/`);
}

export function runCode(slug: string, code: string, language: Language) {
  return request<Submission>(`/questions/${slug}/run/`, {
    method: "POST",
    body: JSON.stringify({ code, language }),
  });
}

export function submitCode(slug: string, code: string, language: Language, solveTimeSeconds?: number | null) {
  return request<Submission>(`/questions/${slug}/submit/`, {
    method: "POST",
    body: JSON.stringify({ code, language, solve_time_seconds: solveTimeSeconds ?? null }),
  });
}

export function getSubmissions(slug: string) {
  return request<SubmissionListItem[]>(`/questions/${slug}/submissions/`);
}

export function getSubmission(id: string) {
  return request<Submission>(`/submissions/${id}/`);
}

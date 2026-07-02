const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api";
const AUTH_TOKEN_KEY = "hackerleap-code-admin-token";

export type Language = "java" | "python";

export type QuestionListItem = {
  id: number;
  title: string;
  slug: string;
  difficulty: "easy" | "medium" | "hard";
  solved: boolean;
  revision_marked: boolean;
  test_case_count: number;
};

export type QuestionDetail = QuestionListItem & {
  description: string;
  starter_code: string;
  java_starter_code: string;
  python_starter_code: string;
  execution_mode: "stdin" | "function";
  function_name: string;
  has_reference_solution: boolean;
};

export type QuestionReferenceSolution = {
  id: number;
  title: string;
  slug: string;
  java_reference_solution: string;
  python_reference_solution: string;
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
  memory_kb: number;
  custom_input: string;
};

export type SubmissionStatus = "pending" | "accepted" | "wrong_answer" | "runtime_error" | "time_limit_exceeded";

export type Submission = {
  id: number;
  question: number;
  question_slug: string;
  question_title: string;
  submission_number: number | null;
  kind: "run" | "submit" | "custom";
  language: Language;
  code: string;
  status: SubmissionStatus;
  stdout: string;
  stderr: string;
  execution_time_ms: number;
  memory_kb: number;
  solve_time_seconds: number | null;
  marked_for_revision: boolean;
  passed_count: number;
  total_count: number;
  created_at: string;
  results: TestCaseResult[];
};

export type CustomTestCasePayload = {
  input: string;
  expected_output?: string;
};

export type SubmissionListItem = Omit<Submission, "code" | "stdout" | "stderr" | "results" | "question">;

export type RevisionSubmission = {
  id: number;
  question_slug: string;
  question_title: string;
  language: Language;
  code: string;
  execution_time_ms: number;
  memory_kb: number;
  created_at: string;
};

export type AuthUser = {
  id: number;
  username: string;
  email: string;
  is_staff: boolean;
  can_access_coding_platform: boolean;
};

export type AuthSession = {
  token: string;
  user: AuthUser;
};

let cachedAuthUser: AuthUser | null = null;
const authListeners = new Set<(user: AuthUser | null) => void>();

function notifyAuthListeners() {
  authListeners.forEach((listener) => listener(cachedAuthUser));
}

export function getCachedAuthUser() {
  return cachedAuthUser;
}

export function setCachedAuthUser(user: AuthUser | null) {
  cachedAuthUser = user;
  notifyAuthListeners();
}

export function subscribeAuthSession(listener: (user: AuthUser | null) => void) {
  authListeners.add(listener);
  return () => authListeners.delete(listener);
}

export function getAuthToken() {
  if (typeof window === "undefined") {
    return null;
  }
  return window.localStorage.getItem(AUTH_TOKEN_KEY);
}

export function setAuthToken(token: string) {
  window.localStorage.setItem(AUTH_TOKEN_KEY, token);
}

export function clearAuthToken() {
  window.localStorage.removeItem(AUTH_TOKEN_KEY);
}

export function clearAuthSession() {
  if (typeof window !== "undefined") {
    clearAuthToken();
  }
  setCachedAuthUser(null);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getAuthToken();
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    if (response.status === 401 || response.status === 403) {
      clearAuthSession();
    }
    throw new Error(detail.detail ?? `Request failed with ${response.status}`);
  }

  return response.json();
}

export async function loginAdmin(username: string, password: string) {
  const session = await request<AuthSession>("/auth/login/", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  setAuthToken(session.token);
  setCachedAuthUser(session.user);
  return session;
}

export async function getCurrentAdmin() {
  const user = await request<AuthUser>("/auth/me/");
  setCachedAuthUser(user);
  return user;
}

export async function logoutAdmin() {
  try {
    await request<{ status: string }>("/auth/logout/", { method: "POST", body: "{}" });
  } finally {
    clearAuthSession();
  }
}

export function getQuestions() {
  return request<QuestionListItem[]>("/questions/");
}

export function getQuestion(slug: string) {
  return request<QuestionDetail>(`/questions/${slug}/`);
}

export function getQuestionReferenceSolution(slug: string) {
  return request<QuestionReferenceSolution>(`/questions/${slug}/reference-solution/`);
}

export function markQuestionForRevision(slug: string, marked: boolean) {
  return request<{ revision_marked: boolean; submission: SubmissionListItem | null }>(`/questions/${slug}/revision/`, {
    method: "POST",
    body: JSON.stringify({ marked }),
  });
}

export function runCode(slug: string, code: string, language: Language) {
  return request<Submission>(`/questions/${slug}/run/`, {
    method: "POST",
    body: JSON.stringify({ code, language }),
  });
}

export function runCustomCode(slug: string, code: string, language: Language, testCases: CustomTestCasePayload[]) {
  return request<Submission>(`/questions/${slug}/custom-run/`, {
    method: "POST",
    body: JSON.stringify({ code, language, test_cases: testCases }),
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

export function getRevisionSubmissions() {
  return request<RevisionSubmission[]>("/revision/");
}

export function getSubmission(id: string) {
  return request<Submission>(`/submissions/${id}/`);
}

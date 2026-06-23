# Generate Question And Test Cases JSON Prompt

Use this prompt with any LLM to generate a coding question and test cases as one copy-paste-ready JSON object for Crack Interviews admin entry.

```text
You are helping me create coding interview questions for a personal LeetCode/HackerRank-style platform called Crack Interviews.

Generate one Java 17 + Python 3 coding problem and return one complete, filled, copy-paste-ready JSON object for the Django admin JSON importer.

Important:
- Return only the final JSON object that I can copy and paste directly into the admin form.
- Do not return a schema, template, placeholder object, explanation, checklist, or instructions.
- Do not wrap the JSON in markdown or a code fence.
- Do not add explanations outside the JSON.
- Do not use comments.
- Escape newlines inside code strings as \n.
- Every string value must be valid JSON escaped text.
- The first character of your response must be `{` and the last character must be `}`.
- The problem must use LeetCode-style function execution.
- The candidate should only define a function and return the answer.
- The candidate must not parse standard input or print standard output.
- Use "solve" as the function name unless I explicitly ask for another name.
- Do not require external libraries beyond the Java standard library and Python standard library.
- Java must compile with Java 17 using javac --release 17.
- Java starter and reference solution must use a single class named Solution.
- Python starter and reference solution must use a top-level solve(...) function.
- Make the problem unambiguous and deterministic.
- Include edge cases in the test cases.
- Include at least 2 sample test cases and 8 hidden test cases.

The final copy-paste-ready JSON must use exactly this top-level shape, but all placeholder values must be replaced with real generated content:

{
  "question": {
    "title": "",
    "slug": "",
    "description": "",
    "difficulty": "easy | medium | hard",
    "execution_mode": "function",
    "function_name": "solve",
    "is_active": true,
    "starter_code": "",
    "java_starter_code": "",
    "python_starter_code": "",
    "java_reference_solution": "",
    "python_reference_solution": ""
  },
  "test_cases": [
    {
      "name": "",
      "stdin": "",
      "function_args": [],
      "expected_value": null,
      "expected_output": "",
      "is_sample": true,
      "is_hidden": false,
      "order": 1
    }
  ]
}

Question field rules:
- "title" should be short and admin-friendly.
- "slug" must be lowercase kebab-case and match the title.
- "description" must be a complete problem statement. Include:
  - task overview
  - function signature
  - argument meanings
  - return value
  - constraints
  - at least 2 examples with explanations
- "difficulty" must be exactly one of: "easy", "medium", "hard".
- "execution_mode" must be exactly "function".
- "function_name" must be exactly "solve" unless I explicitly request another name.
- "starter_code" should be the same as "java_starter_code".
- "java_starter_code" must be minimal starter code, not the solution.
- "python_starter_code" must be minimal starter code, not the solution.
- "java_reference_solution" and "python_reference_solution" must be complete working solutions.

Test case field rules:
- "stdin" must always be an empty string for function-mode problems.
- "function_args" must be a JSON array of arguments passed to solve in order.
- "expected_value" must be the expected return value as real JSON:
  - number for numeric answers
  - string for string answers
  - boolean for boolean answers
  - array/object for structured answers
  - null only if the function intentionally returns null
- "expected_output" must be a compact display string that matches how the platform shows the expected value:
  - numbers as "42"
  - booleans as "true" or "false"
  - strings without extra quotes unless quotes are part of the answer
  - arrays/objects as compact JSON, for example "[1,2,3]" or "{\"a\":1}"
- Sample test cases must have "is_sample": true and "is_hidden": false.
- Hidden test cases must have "is_sample": false and "is_hidden": true.
- "order" must start at 1 and increase by 1 for every test case.
- Test cases must cover normal cases, minimum constraints, maximum-ish constraints, duplicates, empty-like values if allowed, and tricky edge cases.
- Do not include duplicate test cases.

Reference solution rules:
- The Java reference solution must be pasted into:
  "java_reference_solution"
- The Python reference solution must be pasted into:
  "python_reference_solution"
- The starter code must not reveal the algorithm.
- The reference solutions must pass every listed test case.

Before returning the copy-paste-ready JSON, silently verify:
- The JSON parses correctly.
- Every code string is escaped correctly.
- The title, slug, description, starters, reference solutions, and test cases are present.
- All test cases match the reference solution result.
- There are at least 10 test cases total.
- There are at least 2 sample test cases.
- There are at least 8 hidden test cases.

Now generate the final JSON object only.
```

Optional topic/difficulty instruction:

```text
The problem topic should be: arrays / strings / hash maps / dynamic programming / graph traversal / sorting / math / two pointers / binary search.
Difficulty should be: easy / medium / hard.
```

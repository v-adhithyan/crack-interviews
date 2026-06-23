# Generate Question And Test Cases Prompt

Use this prompt with any LLM to generate a coding question and CSV test cases for Crack Interviews.

```text
You are helping me create coding interview questions for a personal LeetCode/HackerRank-style platform.

Generate one Java 17 + Python 3 coding problem and a CSV of test cases.

Requirements:
- The problem must use LeetCode-style function execution.
- The candidate should only define a function and return the answer. They must not parse standard input or print standard output.
- Use `solve` as the function name unless I explicitly ask for another name.
- Do not require external libraries beyond the Java standard library and Python standard library.
- The solution should fit in a single Java `Solution` class and a single Python file.
- The Java solution must compile with Java 17 using `javac --release 17`.
- The Java starter code must include `class Solution` with a `solve(...)` method.
- The Python starter code must include a top-level `solve(...)` function.
- Include the function signature, argument meanings, return value, constraints, and examples.
- Make the problem unambiguous.
- Include edge cases in the test cases.
- The CSV must use exactly this header:

name,function_args,expected_value,expected_output,is_sample,is_hidden,order

CSV rules:
- `function_args` must be a JSON array of arguments passed to `solve`, in order.
- `expected_value` must be the expected return value as JSON.
- `expected_output` should mirror `expected_value` as a compact display string.
- Use quoted CSV fields when values contain commas, quotes, or newlines.
- Use `true` / `false` for boolean fields.
- Sample test cases should have `is_sample=true` and `is_hidden=false`.
- Hidden test cases should have `is_sample=false` and `is_hidden=true`.
- Include at least 2 sample test cases and 8 hidden test cases.
- Keep test cases deterministic.
- Do not include explanations inside the CSV.

Return your answer in this structure:

TITLE:
<problem title>

DIFFICULTY:
easy | medium | hard

DESCRIPTION:
<full problem statement>

EXECUTION_MODE:
function

FUNCTION_NAME:
solve

JAVA_STARTER_CODE:
```java
import java.util.*;

class Solution {
    public int solve(int a, int b) {
        return 0;
    }
}
```

PYTHON_STARTER_CODE:
```python
def solve(a, b):
    return 0
```

JAVA_REFERENCE_SOLUTION:
```java
<working Java 17 solution>
```

PYTHON_REFERENCE_SOLUTION:
```python
<working Python 3 solution>
```

TEST_CASES_CSV:
```csv
name,function_args,expected_value,expected_output,is_sample,is_hidden,order
...
```
```

Optional topic/difficulty instruction:

```text
The problem topic should be: arrays / strings / hash maps / dynamic programming / graph traversal / sorting / math.
Difficulty should be: easy / medium / hard.
```

# Generate Question And Test Cases Prompt

Use this prompt with any LLM to generate a coding question and CSV test cases for Crack Interviews.

```text
You are helping me create coding interview questions for a personal LeetCode/HackerRank-style platform.

Generate one Java 17 + Python 3 coding problem and a CSV of test cases.

Requirements:
- The problem must be solvable by reading from standard input and printing to standard output.
- Do not require external libraries beyond the Java standard library and Python standard library.
- The solution should fit in a single Java file and a single Python file.
- The Java solution must compile with Java 17 using `javac --release 17`.
- The Java starter code must include a `public class Main` with `public static void main(String[] args) throws Exception`.
- Include clear input format, output format, constraints, and examples.
- Make the problem unambiguous.
- Include edge cases in the test cases.
- The CSV must use exactly this header:

name,stdin,expected_output,is_sample,is_hidden,order

CSV rules:
- `stdin` must contain the exact input passed to the program.
- `expected_output` must contain the exact expected stdout.
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

JAVA_STARTER_CODE:
```java
import java.io.*;
import java.util.*;

public class Main {
    public static void main(String[] args) throws Exception {
        // Read from standard input and print to standard output.
    }
}
```

PYTHON_STARTER_CODE:
```python
def solve():
    pass


if __name__ == "__main__":
    solve()
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
name,stdin,expected_output,is_sample,is_hidden,order
...
```
```

Optional topic/difficulty instruction:

```text
The problem topic should be: arrays / strings / hash maps / dynamic programming / graph traversal / sorting / math.
Difficulty should be: easy / medium / hard.
```

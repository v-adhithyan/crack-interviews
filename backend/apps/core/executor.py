import json
import re
import subprocess
import tempfile
import time
from pathlib import Path

from django.conf import settings

from .models import Submission, TestCaseResult


CLASS_PATTERN = re.compile(r"(?:public\s+)?class\s+([A-Za-z_][A-Za-z0-9_]*)")
PUBLIC_CLASS_PATTERN = re.compile(r"public\s+class\s+([A-Za-z_][A-Za-z0-9_]*)")
JAVA_FUNCTION_HARNESS = r"""
import java.io.*;
import java.lang.reflect.*;
import java.util.*;

public class Harness {
    public static void main(String[] args) throws Exception {
        String input = new String(System.in.readAllBytes());
        Object parsed = new JsonParser(input).parseValue();
        List<?> callArgs = parsed instanceof List ? (List<?>) parsed : List.of(parsed);
        Class<?> solutionClass = Class.forName("Solution");
        Method target = null;
        for (Method method : solutionClass.getDeclaredMethods()) {
            if (method.getName().equals("__FUNCTION_NAME__") && method.getParameterCount() == callArgs.size()) {
                target = method;
                break;
            }
        }
        if (target == null) {
            throw new RuntimeException("Could not find method __FUNCTION_NAME__ with " + callArgs.size() + " parameter(s).");
        }
        target.setAccessible(true);
        Object instance = Modifier.isStatic(target.getModifiers()) ? null : solutionClass.getDeclaredConstructor().newInstance();
        Class<?>[] parameterTypes = target.getParameterTypes();
        Object[] convertedArgs = new Object[parameterTypes.length];
        for (int i = 0; i < parameterTypes.length; i++) {
            convertedArgs[i] = convertValue(callArgs.get(i), parameterTypes[i]);
        }
        Object result = target.invoke(instance, convertedArgs);
        System.out.print(toJson(result));
    }

    static Object convertValue(Object value, Class<?> targetType) {
        if (value == null) {
            return null;
        }
        if (targetType == int.class || targetType == Integer.class) {
            return ((Number) value).intValue();
        }
        if (targetType == long.class || targetType == Long.class) {
            return ((Number) value).longValue();
        }
        if (targetType == double.class || targetType == Double.class) {
            return ((Number) value).doubleValue();
        }
        if (targetType == boolean.class || targetType == Boolean.class) {
            return (Boolean) value;
        }
        if (targetType == String.class) {
            return String.valueOf(value);
        }
        if (targetType.isArray() && value instanceof List) {
            List<?> values = (List<?>) value;
            Class<?> componentType = targetType.getComponentType();
            Object array = Array.newInstance(componentType, values.size());
            for (int i = 0; i < values.size(); i++) {
                Array.set(array, i, convertValue(values.get(i), componentType));
            }
            return array;
        }
        if (List.class.isAssignableFrom(targetType) && value instanceof List) {
            return value;
        }
        return value;
    }

    static String toJson(Object value) {
        if (value == null) {
            return "null";
        }
        if (value instanceof Number || value instanceof Boolean) {
            return String.valueOf(value);
        }
        if (value instanceof CharSequence || value instanceof Character) {
            return quote(String.valueOf(value));
        }
        Class<?> valueClass = value.getClass();
        if (valueClass.isArray()) {
            List<String> parts = new ArrayList<>();
            int length = Array.getLength(value);
            for (int i = 0; i < length; i++) {
                parts.add(toJson(Array.get(value, i)));
            }
            return "[" + String.join(",", parts) + "]";
        }
        if (value instanceof Iterable) {
            List<String> parts = new ArrayList<>();
            for (Object item : (Iterable<?>) value) {
                parts.add(toJson(item));
            }
            return "[" + String.join(",", parts) + "]";
        }
        return quote(String.valueOf(value));
    }

    static String quote(String value) {
        StringBuilder builder = new StringBuilder("\"");
        for (int i = 0; i < value.length(); i++) {
            char ch = value.charAt(i);
            if (ch == '"' || ch == '\\') {
                builder.append('\\').append(ch);
            } else if (ch == '\n') {
                builder.append("\\n");
            } else if (ch == '\r') {
                builder.append("\\r");
            } else if (ch == '\t') {
                builder.append("\\t");
            } else {
                builder.append(ch);
            }
        }
        return builder.append("\"").toString();
    }

    static class JsonParser {
        private final String text;
        private int index = 0;

        JsonParser(String text) {
            this.text = text == null ? "" : text;
        }

        Object parseValue() {
            skipWhitespace();
            if (index >= text.length()) {
                return null;
            }
            char ch = text.charAt(index);
            if (ch == '[') {
                return parseArray();
            }
            if (ch == '"') {
                return parseString();
            }
            if (text.startsWith("true", index)) {
                index += 4;
                return true;
            }
            if (text.startsWith("false", index)) {
                index += 5;
                return false;
            }
            if (text.startsWith("null", index)) {
                index += 4;
                return null;
            }
            return parseNumber();
        }

        List<Object> parseArray() {
            index++;
            List<Object> values = new ArrayList<>();
            skipWhitespace();
            if (index < text.length() && text.charAt(index) == ']') {
                index++;
                return values;
            }
            while (index < text.length()) {
                values.add(parseValue());
                skipWhitespace();
                if (index < text.length() && text.charAt(index) == ',') {
                    index++;
                    continue;
                }
                if (index < text.length() && text.charAt(index) == ']') {
                    index++;
                    break;
                }
            }
            return values;
        }

        String parseString() {
            index++;
            StringBuilder builder = new StringBuilder();
            while (index < text.length()) {
                char ch = text.charAt(index++);
                if (ch == '"') {
                    break;
                }
                if (ch == '\\' && index < text.length()) {
                    char escaped = text.charAt(index++);
                    if (escaped == 'n') {
                        builder.append('\n');
                    } else if (escaped == 'r') {
                        builder.append('\r');
                    } else if (escaped == 't') {
                        builder.append('\t');
                    } else {
                        builder.append(escaped);
                    }
                } else {
                    builder.append(ch);
                }
            }
            return builder.toString();
        }

        Number parseNumber() {
            int start = index;
            while (index < text.length() && "-+0123456789.eE".indexOf(text.charAt(index)) >= 0) {
                index++;
            }
            String raw = text.substring(start, index);
            if (raw.contains(".") || raw.contains("e") || raw.contains("E")) {
                return Double.parseDouble(raw);
            }
            return Long.parseLong(raw);
        }

        void skipWhitespace() {
            while (index < text.length() && Character.isWhitespace(text.charAt(index))) {
                index++;
            }
        }
    }
}
"""


def normalize_output(value):
    return value.replace("\r\n", "\n").strip()


def normalized_json_output(value):
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def expected_value_for_test(test_case):
    if test_case.expected_value is not None:
        return test_case.expected_value
    try:
        return json.loads(test_case.expected_output)
    except json.JSONDecodeError:
        return test_case.expected_output


def function_args_for_test(test_case):
    if test_case.function_args is not None:
        return test_case.function_args
    if not test_case.stdin.strip():
        return []
    return json.loads(test_case.stdin)


def class_name_for_java(code):
    public_match = PUBLIC_CLASS_PATTERN.search(code)
    if public_match:
        return public_match.group(1)

    class_names = CLASS_PATTERN.findall(code)
    for preferred in ("Main", "Solution"):
        if preferred in class_names:
            return preferred
    return class_names[0] if class_names else "Main"


def compile_java(code):
    temp_dir = tempfile.TemporaryDirectory()
    class_name = class_name_for_java(code)
    source_path = Path(temp_dir.name) / f"{class_name}.java"
    source_path.write_text(code, encoding="utf-8")
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            [settings.JAVAC_EXECUTABLE, "--release", str(settings.JAVA_RELEASE), str(source_path)],
            text=True,
            capture_output=True,
            timeout=settings.COMPILE_TIMEOUT_SECONDS,
            check=False,
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        if completed.returncode == 0:
            return temp_dir, class_name, "", elapsed_ms
        error = completed.stderr or completed.stdout
    except subprocess.TimeoutExpired as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        error = exc.stderr or exc.stdout or "Compilation timed out."

    if isinstance(error, bytes):
        error = error.decode("utf-8", errors="replace")
    if error:
        temp_dir.cleanup()
        return None, class_name, error, elapsed_ms
    temp_dir.cleanup()
    return None, class_name, "Compilation failed.", elapsed_ms


def compile_java_function(code, function_name):
    temp_dir = tempfile.TemporaryDirectory()
    solution_path = Path(temp_dir.name) / "Solution.java"
    harness_path = Path(temp_dir.name) / "Harness.java"
    solution_path.write_text(code, encoding="utf-8")
    harness_path.write_text(JAVA_FUNCTION_HARNESS.replace("__FUNCTION_NAME__", function_name), encoding="utf-8")
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            [
                settings.JAVAC_EXECUTABLE,
                "--release",
                str(settings.JAVA_RELEASE),
                str(solution_path),
                str(harness_path),
            ],
            text=True,
            capture_output=True,
            timeout=settings.COMPILE_TIMEOUT_SECONDS,
            check=False,
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        if completed.returncode == 0:
            return temp_dir, "", elapsed_ms
        error = completed.stderr or completed.stdout
    except subprocess.TimeoutExpired as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        error = exc.stderr or exc.stdout or "Compilation timed out."

    if isinstance(error, bytes):
        error = error.decode("utf-8", errors="replace")
    temp_dir.cleanup()
    return None, error or "Compilation failed.", elapsed_ms


def python_function_wrapper(code, function_name):
    return (
        "import json\n"
        "import sys\n\n"
        f"{code}\n\n"
        "def __ci_main():\n"
        "    raw_args = sys.stdin.read().strip()\n"
        "    args = json.loads(raw_args) if raw_args else []\n"
        "    if not isinstance(args, list):\n"
        "        args = [args]\n"
        f"    result = {function_name}(*args)\n"
        "    print(json.dumps(result, separators=(',', ':'), sort_keys=True))\n\n"
        "__ci_main()\n"
    )


def run_process_for_test(submission, test_case, java_context=None):
    if submission.language == Submission.Language.JAVA:
        temp_dir, class_name = java_context
        command = [settings.JAVA_EXECUTABLE, "-cp", temp_dir.name, class_name]
    else:
        command = [settings.PYTHON_EXECUTABLE, "-c", submission.code]

    return subprocess.run(
        command,
        input=test_case.stdin,
        text=True,
        capture_output=True,
        timeout=settings.CODE_TIMEOUT_SECONDS,
        check=False,
    )


def run_function_process_for_test(submission, test_case, function_name, java_context=None):
    encoded_args = json.dumps(function_args_for_test(test_case), separators=(",", ":"))
    if submission.language == Submission.Language.JAVA:
        temp_dir = java_context
        command = [settings.JAVA_EXECUTABLE, "-cp", temp_dir.name, "Harness"]
    else:
        command = [settings.PYTHON_EXECUTABLE, "-c", python_function_wrapper(submission.code, function_name)]

    return subprocess.run(
        command,
        input=encoded_args,
        text=True,
        capture_output=True,
        timeout=settings.CODE_TIMEOUT_SECONDS,
        check=False,
    )


def mark_compile_error(submission, test_cases, compile_error, compile_ms, total_start):
    final_status = Submission.Status.RUNTIME_ERROR
    for test_case in test_cases:
        TestCaseResult.objects.create(
            submission=submission,
            test_case=test_case,
            status=final_status,
            stdout="",
            stderr=compile_error,
            expected_output=display_expected_output(test_case),
            execution_time_ms=compile_ms,
        )
    submission.status = final_status
    submission.stdout = ""
    submission.stderr = compile_error
    submission.execution_time_ms = int((time.perf_counter() - total_start) * 1000)
    submission.passed_count = 0
    submission.total_count = len(test_cases)
    submission.save(update_fields=[
        "status",
        "stdout",
        "stderr",
        "execution_time_ms",
        "passed_count",
        "total_count",
    ])
    return submission


def display_expected_output(test_case):
    if test_case.expected_value is not None:
        return normalized_json_output(test_case.expected_value)
    return test_case.expected_output


def run_submission(submission, test_cases):
    total_start = time.perf_counter()
    passed_count = 0
    final_status = Submission.Status.ACCEPTED
    combined_stdout = []
    combined_stderr = []
    test_cases = list(test_cases)
    java_temp_dir = None
    java_class_name = None
    is_function_mode = submission.question.execution_mode == submission.question.ExecutionMode.FUNCTION
    function_name = submission.question.function_name or "solve"

    if submission.language == Submission.Language.JAVA and is_function_mode:
        java_temp_dir, compile_error, compile_ms = compile_java_function(submission.code, function_name)
        if compile_error:
            return mark_compile_error(submission, test_cases, compile_error, compile_ms, total_start)
    elif submission.language == Submission.Language.JAVA:
        java_temp_dir, java_class_name, compile_error, compile_ms = compile_java(submission.code)
        if compile_error:
            return mark_compile_error(submission, test_cases, compile_error, compile_ms, total_start)

    try:
        for test_case in test_cases:
            started = time.perf_counter()
            try:
                if is_function_mode:
                    completed = run_function_process_for_test(
                        submission,
                        test_case,
                        function_name,
                        java_context=java_temp_dir if submission.language == Submission.Language.JAVA else None,
                    )
                else:
                    completed = run_process_for_test(
                        submission,
                        test_case,
                        java_context=(java_temp_dir, java_class_name) if java_temp_dir else None,
                    )
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                stdout = completed.stdout
                stderr = completed.stderr

                if completed.returncode != 0:
                    status = Submission.Status.RUNTIME_ERROR
                elif is_function_mode:
                    try:
                        actual_value = json.loads(normalize_output(stdout))
                        expected_value = expected_value_for_test(test_case)
                    except json.JSONDecodeError:
                        status = Submission.Status.WRONG_ANSWER
                    else:
                        status = Submission.Status.ACCEPTED if actual_value == expected_value else Submission.Status.WRONG_ANSWER
                        passed_count += int(status == Submission.Status.ACCEPTED)
                elif normalize_output(stdout) == normalize_output(test_case.expected_output):
                    status = Submission.Status.ACCEPTED
                    passed_count += 1
                else:
                    status = Submission.Status.WRONG_ANSWER
            except subprocess.TimeoutExpired as exc:
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                stdout = exc.stdout or ""
                stderr = exc.stderr or "Execution timed out."
                status = Submission.Status.TIME_LIMIT_EXCEEDED
            except Exception as exc:
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                stdout = ""
                stderr = str(exc)
                status = Submission.Status.RUNTIME_ERROR

            TestCaseResult.objects.create(
                submission=submission,
                test_case=test_case,
                status=status,
                stdout=stdout,
                stderr=stderr,
                expected_output=display_expected_output(test_case),
                execution_time_ms=elapsed_ms,
            )
            combined_stdout.append(stdout)
            combined_stderr.append(stderr)

            if status != Submission.Status.ACCEPTED and final_status == Submission.Status.ACCEPTED:
                final_status = status
    finally:
        if java_temp_dir:
            java_temp_dir.cleanup()

    submission.status = final_status
    submission.stdout = "\n".join(part for part in combined_stdout if part)
    submission.stderr = "\n".join(part for part in combined_stderr if part)
    submission.execution_time_ms = int((time.perf_counter() - total_start) * 1000)
    submission.passed_count = passed_count
    submission.total_count = len(test_cases)
    submission.save(update_fields=[
        "status",
        "stdout",
        "stderr",
        "execution_time_ms",
        "passed_count",
        "total_count",
    ])
    return submission

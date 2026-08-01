import json
import re
import resource
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from django.conf import settings

from .models import Submission, TestCaseResult


CLASS_PATTERN = re.compile(r"(?:public\s+)?class\s+([A-Za-z_][A-Za-z0-9_]*)")
PUBLIC_CLASS_PATTERN = re.compile(r"public\s+class\s+([A-Za-z_][A-Za-z0-9_]*)")
MEMORY_MARKER = "__HACKERLEAP_MEMORY_KB__:"
MACOS_MEMORY_PATTERN = re.compile(r"^\s*(\d+)\s+maximum resident set size", re.MULTILINE)
JAVA_FUNCTION_HARNESS = r"""
import java.io.*;
import java.lang.reflect.*;
import java.util.*;

public class Harness {
    public static void main(String[] args) throws Exception {
        String input = readInput();
        Object parsed = new JsonParser(input).parseValue();
        List<?> callArgs = parsed instanceof List ? (List<?>) parsed : Collections.singletonList(parsed);
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
        System.out.print(serializeResult(result, target.getReturnType()));
    }

    static String readInput() throws IOException {
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        byte[] buffer = new byte[4096];
        int bytesRead;
        while ((bytesRead = System.in.read(buffer)) != -1) {
            output.write(buffer, 0, bytesRead);
        }
        return new String(output.toByteArray(), "UTF-8");
    }

    static Object convertValue(Object value, Class<?> targetType) {
        if (value == null) {
            return null;
        }
        if (targetType.getSimpleName().equals("ListNode") && value instanceof List) {
            return buildListNode((List<?>) value, targetType);
        }
        if (targetType.getSimpleName().equals("TreeNode") && value instanceof List) {
            return buildTreeNode((List<?>) value, targetType);
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

    static Object newNode(Class<?> nodeType, int value) {
        try {
            Constructor<?> constructor = nodeType.getDeclaredConstructor(int.class);
            constructor.setAccessible(true);
            return constructor.newInstance(value);
        } catch (ReflectiveOperationException ignored) {
            try {
                Constructor<?> constructor = nodeType.getDeclaredConstructor();
                constructor.setAccessible(true);
                Object node = constructor.newInstance();
                Field valueField = nodeType.getDeclaredField("val");
                valueField.setAccessible(true);
                valueField.set(node, value);
                return node;
            } catch (ReflectiveOperationException error) {
                throw new RuntimeException("ListNode/TreeNode must provide a no-argument or int constructor and a val field.", error);
            }
        }
    }

    static Object buildListNode(List<?> values, Class<?> nodeType) {
        Object head = null;
        Object tail = null;
        try {
            Field nextField = nodeType.getDeclaredField("next");
            nextField.setAccessible(true);
            for (Object value : values) {
                if (value == null) {
                    continue;
                }
                Object node = newNode(nodeType, ((Number) value).intValue());
                if (head == null) {
                    head = node;
                } else {
                    nextField.set(tail, node);
                }
                tail = node;
            }
            return head;
        } catch (ReflectiveOperationException error) {
            throw new RuntimeException("ListNode must expose a next field.", error);
        }
    }

    static Object buildTreeNode(List<?> values, Class<?> nodeType) {
        if (values.isEmpty() || values.get(0) == null) {
            return null;
        }
        try {
            Field leftField = nodeType.getDeclaredField("left");
            Field rightField = nodeType.getDeclaredField("right");
            leftField.setAccessible(true);
            rightField.setAccessible(true);
            Object root = newNode(nodeType, ((Number) values.get(0)).intValue());
            Queue<Object> queue = new ArrayDeque<>();
            queue.add(root);
            int index = 1;
            while (!queue.isEmpty() && index < values.size()) {
                Object parent = queue.remove();
                Object leftValue = values.get(index++);
                if (leftValue != null) {
                    Object left = newNode(nodeType, ((Number) leftValue).intValue());
                    leftField.set(parent, left);
                    queue.add(left);
                }
                if (index < values.size()) {
                    Object rightValue = values.get(index++);
                    if (rightValue != null) {
                        Object right = newNode(nodeType, ((Number) rightValue).intValue());
                        rightField.set(parent, right);
                        queue.add(right);
                    }
                }
            }
            return root;
        } catch (ReflectiveOperationException error) {
            throw new RuntimeException("TreeNode must expose left and right fields.", error);
        }
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
        if (value.getClass().getSimpleName().equals("ListNode")) {
            return listNodeToJson(value);
        }
        if (value.getClass().getSimpleName().equals("TreeNode")) {
            return treeNodeValueToJson(value);
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

    static String serializeResult(Object value, Class<?> returnType) {
        if (value == null && returnType.getSimpleName().equals("ListNode")) {
            return "[]";
        }
        return toJson(value);
    }

    static String listNodeToJson(Object head) {
        List<String> values = new ArrayList<>();
        Object current = head;
        try {
            Field valueField = head.getClass().getDeclaredField("val");
            Field nextField = head.getClass().getDeclaredField("next");
            valueField.setAccessible(true);
            nextField.setAccessible(true);
            while (current != null) {
                values.add(toJson(valueField.get(current)));
                current = nextField.get(current);
            }
            return "[" + String.join(",", values) + "]";
        } catch (ReflectiveOperationException error) {
            throw new RuntimeException("ListNode must expose val and next fields.", error);
        }
    }

    static String treeNodeValueToJson(Object node) {
        try {
            Field valueField = node.getClass().getDeclaredField("val");
            valueField.setAccessible(true);
            return toJson(valueField.get(node));
        } catch (ReflectiveOperationException error) {
            throw new RuntimeException("TreeNode must expose a val field.", error);
        }
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


def canonical_json(value):
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def values_match(question, actual_value, expected_value):
    mode = question.comparison_mode
    if mode == question.ComparisonMode.ORDERED:
        return actual_value == expected_value
    if not isinstance(actual_value, list) or not isinstance(expected_value, list):
        return False
    if mode == question.ComparisonMode.UNORDERED_LIST:
        return sorted(actual_value, key=canonical_json) == sorted(expected_value, key=canonical_json)
    if mode == question.ComparisonMode.UNORDERED_NESTED_LISTS:
        actual_groups = [sorted(group, key=canonical_json) if isinstance(group, list) else group for group in actual_value]
        expected_groups = [sorted(group, key=canonical_json) if isinstance(group, list) else group for group in expected_value]
        return sorted(actual_groups, key=canonical_json) == sorted(expected_groups, key=canonical_json)
    return False


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


def javac_command(source_paths):
    source_paths = [str(path) for path in source_paths]
    if settings.JAVA_RELEASE <= 8:
        release = str(settings.JAVA_RELEASE)
        return [settings.JAVAC_EXECUTABLE, "-source", release, "-target", release, *source_paths]
    return [settings.JAVAC_EXECUTABLE, "--release", str(settings.JAVA_RELEASE), *source_paths]


def measured_command(command, output_path):
    time_executable = shutil.which("time") or "/usr/bin/time"
    if not Path(time_executable).exists():
        return command, None
    if sys.platform == "darwin":
        return [time_executable, "-l", "-o", output_path, *command], "darwin"
    return [time_executable, "-f", f"{MEMORY_MARKER}%M", "-o", output_path, *command], "linux"


def parse_memory_output(output_path, mode):
    if mode is None:
        return 0

    try:
        output = Path(output_path).read_text(encoding="utf-8")
    except OSError:
        return 0

    if mode == "linux":
        for line in output.splitlines():
            if line.startswith(MEMORY_MARKER):
                try:
                    return int(line.removeprefix(MEMORY_MARKER).strip())
                except ValueError:
                    pass
        return 0

    if mode == "darwin":
        match = MACOS_MEMORY_PATTERN.search(output)
        return int(match.group(1)) // 1024 if match else 0

    return 0


def run_measured_process(command, input_value):
    before_usage_kb = child_memory_usage_kb()
    with tempfile.NamedTemporaryFile(prefix="hackerleap-memory-", delete=True) as memory_file:
        wrapped_command, measurement_mode = measured_command(command, memory_file.name)
        completed = subprocess.run(
            wrapped_command,
            input=input_value,
            text=True,
            capture_output=True,
            timeout=settings.CODE_TIMEOUT_SECONDS,
            check=False,
        )
        memory_kb = parse_memory_output(memory_file.name, measurement_mode)
        if not memory_kb:
            after_usage_kb = child_memory_usage_kb()
            memory_kb = max(0, after_usage_kb - before_usage_kb) or after_usage_kb
        return completed, memory_kb


def child_memory_usage_kb():
    max_rss = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    if sys.platform == "darwin":
        return max_rss // 1024
    return max_rss


def compile_java(code):
    temp_dir = tempfile.TemporaryDirectory()
    class_name = class_name_for_java(code)
    source_path = Path(temp_dir.name) / f"{class_name}.java"
    source_path.write_text(code, encoding="utf-8")
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            javac_command([source_path]),
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
            javac_command([solution_path, harness_path]),
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
        "import inspect\n"
        "import sys\n\n"
        f"{code}\n\n"
        "def __ci_list_node(values):\n"
        "    dummy = ListNode(0)\n"
        "    tail = dummy\n"
        "    for value in values:\n"
        "        tail.next = ListNode(value)\n"
        "        tail = tail.next\n"
        "    return dummy.next\n\n"
        "def __ci_tree_node(values):\n"
        "    if not values or values[0] is None:\n"
        "        return None\n"
        "    root = TreeNode(values[0])\n"
        "    queue = [root]\n"
        "    index = 1\n"
        "    while queue and index < len(values):\n"
        "        node = queue.pop(0)\n"
        "        if values[index] is not None:\n"
        "            node.left = TreeNode(values[index])\n"
        "            queue.append(node.left)\n"
        "        index += 1\n"
        "        if index < len(values) and values[index] is not None:\n"
        "            node.right = TreeNode(values[index])\n"
        "            queue.append(node.right)\n"
        "        index += 1\n"
        "    return root\n\n"
        "def __ci_serialize(value, parameter_names):\n"
        "    if value is None and 'ListNode' in globals() and 'head' in parameter_names:\n"
        "        return []\n"
        "    if 'ListNode' in globals() and isinstance(value, ListNode):\n"
        "        result = []\n"
        "        while value is not None:\n"
        "            result.append(value.val)\n"
        "            value = value.next\n"
        "        return result\n"
        "    if 'TreeNode' in globals() and isinstance(value, TreeNode):\n"
        "        return value.val\n"
        "    return value\n\n"
        "def __ci_main():\n"
        "    raw_args = sys.stdin.read().strip()\n"
        "    args = json.loads(raw_args) if raw_args else []\n"
        "    if not isinstance(args, list):\n"
        "        args = [args]\n"
        f"    parameter_names = list(inspect.signature({function_name}).parameters)\n"
        "    converted = []\n"
        "    for index, value in enumerate(args):\n"
        "        name = parameter_names[index] if index < len(parameter_names) else ''\n"
        "        if name == 'head' and 'ListNode' in globals() and isinstance(value, list):\n"
        "            value = __ci_list_node(value)\n"
        "        elif name == 'root' and 'TreeNode' in globals() and isinstance(value, list):\n"
        "            value = __ci_tree_node(value)\n"
        "        converted.append(value)\n"
        f"    result = {function_name}(*converted)\n"
        "    print(json.dumps(__ci_serialize(result, parameter_names), separators=(',', ':'), sort_keys=True))\n\n"
        "__ci_main()\n"
    )


def run_process_for_test(submission, test_case, java_context=None):
    if submission.language == Submission.Language.JAVA:
        temp_dir, class_name = java_context
        command = [settings.JAVA_EXECUTABLE, "-cp", temp_dir.name, class_name]
    else:
        command = [settings.PYTHON_EXECUTABLE, "-c", submission.code]

    return run_measured_process(command, test_case.stdin)


def run_function_process_for_test(submission, test_case, function_name, java_context=None):
    encoded_args = json.dumps(function_args_for_test(test_case), separators=(",", ":"))
    if submission.language == Submission.Language.JAVA:
        temp_dir = java_context
        command = [settings.JAVA_EXECUTABLE, "-cp", temp_dir.name, "Harness"]
    else:
        command = [settings.PYTHON_EXECUTABLE, "-c", python_function_wrapper(submission.code, function_name)]

    return run_measured_process(command, encoded_args)


def mark_compile_error(submission, test_cases, compile_error, compile_ms, total_start):
    final_status = Submission.Status.RUNTIME_ERROR
    for test_case in test_cases:
        TestCaseResult.objects.create(
            submission=submission,
            test_case=test_case if getattr(test_case, "pk", None) else None,
            custom_name=getattr(test_case, "custom_name", ""),
            custom_input=getattr(test_case, "custom_input", ""),
            status=final_status,
            stdout="",
            stderr=compile_error,
            expected_output=display_expected_output(test_case),
            execution_time_ms=compile_ms,
            memory_kb=0,
        )
    submission.status = final_status
    submission.stdout = ""
    submission.stderr = compile_error
    submission.execution_time_ms = int((time.perf_counter() - total_start) * 1000)
    submission.memory_kb = 0
    submission.passed_count = 0
    submission.total_count = len(test_cases)
    submission.save(update_fields=[
        "status",
        "stdout",
        "stderr",
        "execution_time_ms",
        "memory_kb",
        "passed_count",
        "total_count",
    ])
    return submission


def display_expected_output(test_case):
    if not getattr(test_case, "has_expected_output", True):
        return ""
    if test_case.expected_value is not None:
        return normalized_json_output(test_case.expected_value)
    return test_case.expected_output


def run_submission(submission, test_cases):
    total_start = time.perf_counter()
    passed_count = 0
    peak_memory_kb = 0
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
            memory_kb = 0
            try:
                if is_function_mode:
                    completed, memory_kb = run_function_process_for_test(
                        submission,
                        test_case,
                        function_name,
                        java_context=java_temp_dir if submission.language == Submission.Language.JAVA else None,
                    )
                else:
                    completed, memory_kb = run_process_for_test(
                        submission,
                        test_case,
                        java_context=(java_temp_dir, java_class_name) if java_temp_dir else None,
                    )
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                stdout = completed.stdout
                stderr = completed.stderr

                if completed.returncode != 0:
                    status = Submission.Status.RUNTIME_ERROR
                elif not getattr(test_case, "has_expected_output", True):
                    status = Submission.Status.ACCEPTED
                elif is_function_mode:
                    try:
                        actual_value = json.loads(normalize_output(stdout))
                        expected_value = expected_value_for_test(test_case)
                    except json.JSONDecodeError:
                        status = Submission.Status.WRONG_ANSWER
                    else:
                        status = Submission.Status.ACCEPTED if values_match(submission.question, actual_value, expected_value) else Submission.Status.WRONG_ANSWER
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

            peak_memory_kb = max(peak_memory_kb, memory_kb)
            TestCaseResult.objects.create(
                submission=submission,
                test_case=test_case if getattr(test_case, "pk", None) else None,
                custom_name=getattr(test_case, "custom_name", ""),
                custom_input=getattr(test_case, "custom_input", ""),
                status=status,
                stdout=stdout,
                stderr=stderr,
                expected_output=display_expected_output(test_case),
                execution_time_ms=elapsed_ms,
                memory_kb=memory_kb,
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
    submission.memory_kb = peak_memory_kb
    submission.passed_count = passed_count
    submission.total_count = len(test_cases)
    submission.save(update_fields=[
        "status",
        "stdout",
        "stderr",
        "execution_time_ms",
        "memory_kb",
        "passed_count",
        "total_count",
    ])
    return submission

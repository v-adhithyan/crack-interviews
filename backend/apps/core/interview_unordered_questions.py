"""Questions whose collection outputs have no semantic ordering."""

UNORDERED_COMPARISON_MODES = {
    "Group Anagrams": "unordered_nested_lists",
    "Letter Combinations of a Phone Number": "unordered_list",
}

OUTPUT_ORDER_NOTES = {
    "Group Anagrams": (
        "Return one list for each anagram group. The groups may be returned in any order, "
        "and the strings within each group may also be in any order."
    ),
    "Letter Combinations of a Phone Number": "Return all possible combinations in any order.",
}


def phone_combinations(digits):
    if not digits:
        return []
    letters = {
        "2": "abc", "3": "def", "4": "ghi", "5": "jkl",
        "6": "mno", "7": "pqrs", "8": "tuv", "9": "wxyz",
    }
    combinations = [""]
    for digit in digits:
        combinations = [prefix + letter for prefix in combinations for letter in letters[digit]]
    return combinations


UNORDERED_CASES = {
    "Group Anagrams": [
        ([["eat", "tea", "tan", "ate", "nat", "bat"]], [["eat", "tea", "ate"], ["tan", "nat"], ["bat"]]),
        ([[""]], [[""]]),
        ([["a"]], [["a"]]),
        ([["ab", "ba", "abc", "cab", "bca"]], [["ab", "ba"], ["abc", "cab", "bca"]]),
        ([["", ""]], [["", ""]]),
        ([["dddd", "dd", "d"]], [["dddd"], ["dd"], ["d"]]),
        ([["listen", "silent", "enlist", "google", "gooegl"]], [["listen", "silent", "enlist"], ["google", "gooegl"]]),
        ([["rat", "tar", "art", "star", "tars"]], [["rat", "tar", "art"], ["star", "tars"]]),
        ([["abc", "abc", "bca"]], [["abc", "abc", "bca"]]),
        ([["no", "on", "is", "si", "it"]], [["no", "on"], ["is", "si"], ["it"]]),
    ],
    "Letter Combinations of a Phone Number": [
        (["23"], phone_combinations("23")),
        ([""], []),
        (["2"], phone_combinations("2")),
        (["7"], phone_combinations("7")),
        (["9"], phone_combinations("9")),
        (["22"], phone_combinations("22")),
        (["27"], phone_combinations("27")),
        (["79"], phone_combinations("79")),
        (["89"], phone_combinations("89")),
        (["234"], phone_combinations("234")),
    ],
}


JAVA_REFERENCE_SOLUTIONS = {
    "Group Anagrams": """import java.util.*;

class Solution {
    public List<List<String>> solve(String[] strs) {
        Map<String, List<String>> groups = new HashMap<>();
        for (String value : strs) {
            char[] characters = value.toCharArray();
            Arrays.sort(characters);
            String key = new String(characters);
            groups.computeIfAbsent(key, ignored -> new ArrayList<>()).add(value);
        }
        return new ArrayList<>(groups.values());
    }
}
""",
    "Letter Combinations of a Phone Number": """import java.util.*;

class Solution {
    private static final String[] LETTERS = {
        "", "", "abc", "def", "ghi", "jkl", "mno", "pqrs", "tuv", "wxyz"
    };

    public List<String> solve(String digits) {
        List<String> result = new ArrayList<>();
        if (digits.isEmpty()) return result;
        build(digits, 0, new StringBuilder(), result);
        return result;
    }

    private void build(String digits, int index, StringBuilder current, List<String> result) {
        if (index == digits.length()) {
            result.add(current.toString());
            return;
        }
        String choices = LETTERS[digits.charAt(index) - '0'];
        for (int i = 0; i < choices.length(); i++) {
            current.append(choices.charAt(i));
            build(digits, index + 1, current, result);
            current.deleteCharAt(current.length() - 1);
        }
    }
}
""",
}

PYTHON_REFERENCE_SOLUTIONS = {
    "Group Anagrams": """def solve(strs):
    groups = {}
    for value in strs:
        key = ''.join(sorted(value))
        groups.setdefault(key, []).append(value)
    return list(groups.values())
""",
    "Letter Combinations of a Phone Number": """def solve(digits):
    if not digits:
        return []
    letters = {
        '2': 'abc', '3': 'def', '4': 'ghi', '5': 'jkl',
        '6': 'mno', '7': 'pqrs', '8': 'tuv', '9': 'wxyz',
    }
    result = ['']
    for digit in digits:
        result = [prefix + letter for prefix in result for letter in letters[digit]]
    return result
""",
}

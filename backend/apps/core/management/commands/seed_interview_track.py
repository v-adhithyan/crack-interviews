import json

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from apps.core.interview_node_questions import LINKED_LIST_TITLES, NODE_CASES, NODE_TITLES
from apps.core.interview_node_questions import build_java_reference as build_node_java_reference
from apps.core.interview_node_questions import build_java_starter as build_node_java_starter
from apps.core.interview_node_questions import build_python_reference as build_node_python_reference
from apps.core.interview_node_questions import build_python_starter as build_node_python_starter
from apps.core.interview_unordered_questions import JAVA_REFERENCE_SOLUTIONS as UNORDERED_JAVA_SOLUTIONS
from apps.core.interview_unordered_questions import OUTPUT_ORDER_NOTES, PYTHON_REFERENCE_SOLUTIONS as UNORDERED_PYTHON_SOLUTIONS
from apps.core.interview_unordered_questions import UNORDERED_CASES, UNORDERED_COMPARISON_MODES
from apps.core.models import Question, Tag, TestCase, Track, TrackQuestion, TrackSection


TRACK = {
    "title": "Interview Preparation",
    "slug": "interview-preparation",
    "description": (
        "A focused 50-problem path inspired by LeetCode 75, with a 20/60/20 "
        "easy/medium/hard split across the core coding interview patterns."
    ),
    "is_active": True,
}

PROBLEMS = [
    ("Foundations", "Two Sum", "easy", ["array", "hashmap"]),
    ("Foundations", "Merge Strings Alternately", "easy", ["string", "two-pointers"]),
    ("Foundations", "Move Zeroes", "easy", ["array", "two-pointers"]),
    ("Foundations", "Is Subsequence", "easy", ["string", "two-pointers"]),
    ("Foundations", "Find Pivot Index", "easy", ["array", "prefix-sum"]),
    ("Foundations", "Unique Number of Occurrences", "easy", ["hashmap", "hashset"]),
    ("Foundations", "Valid Parentheses", "easy", ["stack", "string"]),
    ("Foundations", "Reverse Linked List", "easy", ["linked-list"]),
    ("Foundations", "Maximum Depth of Binary Tree", "easy", ["tree", "dfs"]),
    ("Foundations", "Counting Bits", "easy", ["bit-manipulation", "dynamic-programming"]),
    ("Arrays, Strings, and Hashing", "Product of Array Except Self", "medium", ["array", "prefix-sum"]),
    ("Arrays, Strings, and Hashing", "Group Anagrams", "medium", ["string", "hashmap"]),
    ("Arrays, Strings, and Hashing", "Longest Consecutive Sequence", "medium", ["array", "hashset"]),
    ("Arrays, Strings, and Hashing", "String Compression", "medium", ["string", "two-pointers"]),
    ("Two Pointers and Sliding Window", "Container With Most Water", "medium", ["array", "two-pointers"]),
    ("Two Pointers and Sliding Window", "Max Number of K-Sum Pairs", "medium", ["array", "two-pointers", "hashmap"]),
    ("Two Pointers and Sliding Window", "Longest Substring Without Repeating Characters", "medium", ["string", "sliding-window"]),
    ("Two Pointers and Sliding Window", "Max Consecutive Ones III", "medium", ["array", "sliding-window"]),
    ("Two Pointers and Sliding Window", "Longest Subarray of 1s After Deleting One", "medium", ["array", "sliding-window"]),
    ("Hashing and Matrix", "Determine if Two Strings Are Close", "medium", ["string", "hashmap"]),
    ("Hashing and Matrix", "Equal Row and Column Pairs", "medium", ["matrix", "hashmap"]),
    ("Stack and Binary Search", "Decode String", "medium", ["stack", "string"]),
    ("Stack and Binary Search", "Asteroid Collision", "medium", ["stack"]),
    ("Stack and Binary Search", "Daily Temperatures", "medium", ["stack", "monotonic-stack"]),
    ("Stack and Binary Search", "Koko Eating Bananas", "medium", ["binary-search"]),
    ("Stack and Binary Search", "Search in Rotated Sorted Array", "medium", ["binary-search"]),
    ("Linked Lists and Design", "Delete the Middle Node of a Linked List", "medium", ["linked-list", "two-pointers"]),
    ("Linked Lists and Design", "Odd Even Linked List", "medium", ["linked-list"]),
    ("Linked Lists and Design", "Maximum Twin Sum of a Linked List", "medium", ["linked-list", "two-pointers"]),
    ("Linked Lists and Design", "LRU Cache", "medium", ["hashmap", "linked-list", "design"]),
    ("Trees", "Count Good Nodes in Binary Tree", "medium", ["tree", "dfs"]),
    ("Trees", "Path Sum III", "medium", ["tree", "dfs", "prefix-sum"]),
    ("Trees", "Lowest Common Ancestor of a Binary Tree", "medium", ["tree", "dfs"]),
    ("Trees", "Binary Tree Right Side View", "medium", ["tree", "bfs"]),
    ("Graphs and Heaps", "Number of Provinces", "medium", ["graph", "dfs", "union-find"]),
    ("Graphs and Heaps", "Rotting Oranges", "medium", ["graph", "bfs", "matrix"]),
    ("Graphs and Heaps", "Course Schedule", "medium", ["graph", "topological-sort"]),
    ("Graphs and Heaps", "Kth Largest Element in an Array", "medium", ["heap"]),
    ("Backtracking and Dynamic Programming", "Letter Combinations of a Phone Number", "medium", ["backtracking"]),
    ("Backtracking and Dynamic Programming", "House Robber", "medium", ["dynamic-programming"]),
    ("Backtracking and Dynamic Programming", "Unique Paths", "medium", ["dynamic-programming"]),
    ("Backtracking and Dynamic Programming", "Longest Common Subsequence", "medium", ["dynamic-programming"]),
    ("Backtracking and Dynamic Programming", "Implement Trie", "medium", ["trie", "design"]),
    ("Backtracking and Dynamic Programming", "Non-overlapping Intervals", "medium", ["intervals", "greedy"]),
    ("Backtracking and Dynamic Programming", "Online Stock Span", "medium", ["stack", "monotonic-stack"]),
    ("Hard Interview Patterns", "Trapping Rain Water", "hard", ["array", "two-pointers"]),
    ("Hard Interview Patterns", "Minimum Window Substring", "hard", ["string", "sliding-window"]),
    ("Hard Interview Patterns", "Sliding Window Maximum", "hard", ["array", "queue", "sliding-window"]),
    ("Hard Interview Patterns", "Largest Rectangle in Histogram", "hard", ["stack", "monotonic-stack"]),
    ("Hard Interview Patterns", "Edit Distance", "hard", ["dynamic-programming", "string"]),
]

SECTION_DESCRIPTIONS = {
    "Foundations": "Warm up with the core building blocks used everywhere else.",
    "Arrays, Strings, and Hashing": "Practice frequency maps, prefix products, and sequence normalization.",
    "Two Pointers and Sliding Window": "Learn how to maintain moving boundaries without brute force.",
    "Hashing and Matrix": "Use hash-based representations to compare richer structures.",
    "Stack and Binary Search": "Cover parser-like stack problems and answer-space search.",
    "Linked Lists and Design": "Practice pointer rewiring and stateful data structure design.",
    "Trees": "Build recursive and level-order reasoning for binary trees.",
    "Graphs and Heaps": "Cover traversal, dependency ordering, and priority access.",
    "Backtracking and Dynamic Programming": "Move from search trees into overlapping subproblems.",
    "Hard Interview Patterns": "Finish with high-signal problems that stress pattern mastery.",
}

PROBLEM_BRIEFS = {
    "Two Sum": "Given an integer array and a target, return the indices of two different elements whose sum equals the target.",
    "Merge Strings Alternately": "Merge two strings by alternating characters from each string, appending any remaining suffix at the end.",
    "Move Zeroes": "Move every zero in an integer array to the end while preserving the relative order of non-zero values.",
    "Is Subsequence": "Return whether all characters of one string appear in another string in the same relative order.",
    "Find Pivot Index": "Find an index where the sum of values to the left equals the sum of values to the right.",
    "Unique Number of Occurrences": "Return whether every distinct number in an array has a unique occurrence count.",
    "Valid Parentheses": "Decide whether a string containing bracket characters is properly opened and closed.",
    "Reverse Linked List": "Given a linked list represented by its values, return the values after reversing the list.",
    "Maximum Depth of Binary Tree": "Given a binary tree in level-order form, return the number of nodes on the longest root-to-leaf path.",
    "Counting Bits": "For every integer from 0 through n, return the number of set bits in its binary representation.",
    "Product of Array Except Self": "Return an array where each position contains the product of all other positions without using division.",
    "Group Anagrams": "Group words that contain the same letters with the same frequencies.",
    "Longest Consecutive Sequence": "Find the length of the longest run of consecutive integer values in an unsorted array.",
    "String Compression": "Compress consecutive repeated characters in-place style by writing each character followed by its count when the count is greater than one.",
    "Container With Most Water": "Choose two vertical lines that, together with the x-axis, hold the largest amount of water.",
    "Max Number of K-Sum Pairs": "Return the maximum number of disjoint pairs whose values add up to k.",
    "Longest Substring Without Repeating Characters": "Find the length of the longest substring containing no repeated characters.",
    "Max Consecutive Ones III": "Find the longest subarray containing only ones after flipping at most k zeroes.",
    "Longest Subarray of 1s After Deleting One": "Delete exactly one element and return the longest remaining contiguous block of ones.",
    "Determine if Two Strings Are Close": "Return whether two strings can be made equal using swaps and global character renames.",
    "Equal Row and Column Pairs": "Count row-column pairs in a square matrix that contain exactly the same sequence.",
    "Decode String": "Decode a string where patterns like 3[ab] repeat the bracketed content.",
    "Asteroid Collision": "Simulate moving asteroids and return the survivors after collisions.",
    "Daily Temperatures": "For each day, return how many days must pass before a warmer temperature appears.",
    "Koko Eating Bananas": "Find the minimum integer eating speed that finishes all piles within h hours.",
    "Search in Rotated Sorted Array": "Find a target value in a sorted array that has been rotated at an unknown pivot.",
    "Delete the Middle Node of a Linked List": "Given linked-list values, delete the middle node and return the remaining values.",
    "Odd Even Linked List": "Reorder linked-list values so nodes in odd positions appear before nodes in even positions.",
    "Maximum Twin Sum of a Linked List": "Pair the first and last linked-list nodes, second and second-last nodes, and return the maximum twin sum.",
    "LRU Cache": "Process cache operations and return lookup results while evicting the least recently used key when capacity is exceeded.",
    "Count Good Nodes in Binary Tree": "Count nodes whose value is at least every value seen on the path from the root.",
    "Path Sum III": "Count downward paths in a binary tree whose values sum to the target.",
    "Lowest Common Ancestor of a Binary Tree": "Return the value of the lowest node that has both requested nodes in its subtree.",
    "Binary Tree Right Side View": "Return the values visible when a binary tree is viewed from the right side.",
    "Number of Provinces": "Given an adjacency matrix of connected cities, count connected components.",
    "Rotting Oranges": "Return how many minutes it takes for all reachable fresh oranges in a grid to rot.",
    "Course Schedule": "Return whether all courses can be completed given prerequisite pairs.",
    "Kth Largest Element in an Array": "Return the kth largest value in an unsorted array.",
    "Letter Combinations of a Phone Number": "Return all possible letter strings represented by telephone keypad digits.",
    "House Robber": "Return the maximum money that can be robbed without robbing adjacent houses.",
    "Unique Paths": "Count paths from the top-left to bottom-right of an m by n grid using only right and down moves.",
    "Longest Common Subsequence": "Return the length of the longest sequence that appears in both strings in order.",
    "Implement Trie": "Process trie insert/search/startsWith operations and return the boolean operation results.",
    "Non-overlapping Intervals": "Return the minimum number of intervals to remove so the rest do not overlap.",
    "Online Stock Span": "For each stock price, return the number of consecutive prior days with price less than or equal to today's price.",
    "Trapping Rain Water": "Given bar heights, compute how much rain water is trapped after raining.",
    "Minimum Window Substring": "Return the shortest substring of s containing every character from t with required multiplicities.",
    "Sliding Window Maximum": "Return the maximum value in each window of size k as it slides across the array.",
    "Largest Rectangle in Histogram": "Given histogram bar heights, return the largest rectangle area that can be formed.",
    "Edit Distance": "Return the minimum insert, delete, or replace operations needed to convert one word into another.",
}

SAMPLE_CASES = {
    "Two Sum": [("[2,7,11,15], target = 9", "[0,1]"), ("[3,2,4], target = 6", "[1,2]")],
    "Merge Strings Alternately": [('"abc", "pqr"', '"apbqcr"'), ('"ab", "pqrs"', '"apbqrs"')],
    "Move Zeroes": [("[0,1,0,3,12]", "[1,3,12,0,0]"), ("[0,0,1]", "[1,0,0]")],
    "Is Subsequence": [('"abc", "ahbgdc"', "true"), ('"axc", "ahbgdc"', "false")],
    "Find Pivot Index": [("[1,7,3,6,5,6]", "3"), ("[1,2,3]", "-1")],
    "Unique Number of Occurrences": [("[1,2,2,1,1,3]", "true"), ("[1,2]", "false")],
    "Valid Parentheses": [('"()[]{}"', "true"), ('"(]"', "false")],
    "Reverse Linked List": [("[1,2,3,4,5]", "[5,4,3,2,1]"), ("[1,2]", "[2,1]")],
    "Maximum Depth of Binary Tree": [("[3,9,20,null,null,15,7]", "3"), ("[1,null,2]", "2")],
    "Counting Bits": [("n = 5", "[0,1,1,2,1,2]"), ("n = 2", "[0,1,1]")],
    "Product of Array Except Self": [("[1,2,3,4]", "[24,12,8,6]"), ("[-1,1,0,-3,3]", "[0,0,9,0,0]")],
    "Group Anagrams": [('["eat","tea","tan","ate","nat","bat"]', '[["bat"],["nat","tan"],["ate","eat","tea"]]')],
    "Longest Consecutive Sequence": [("[100,4,200,1,3,2]", "4"), ("[0,3,7,2,5,8,4,6,0,1]", "9")],
    "String Compression": [('["a","a","b","b","c","c","c"]', '["a","2","b","2","c","3"]')],
    "Container With Most Water": [("[1,8,6,2,5,4,8,3,7]", "49"), ("[1,1]", "1")],
    "Max Number of K-Sum Pairs": [("[1,2,3,4], k = 5", "2"), ("[3,1,3,4,3], k = 6", "1")],
    "Longest Substring Without Repeating Characters": [('"abcabcbb"', "3"), ('"bbbbb"', "1")],
    "Max Consecutive Ones III": [("[1,1,1,0,0,0,1,1,1,1,0], k = 2", "6")],
    "Longest Subarray of 1s After Deleting One": [("[1,1,0,1]", "3"), ("[1,1,1]", "2")],
    "Determine if Two Strings Are Close": [('"abc", "bca"', "true"), ('"a", "aa"', "false")],
    "Equal Row and Column Pairs": [("[[3,2,1],[1,7,6],[2,7,7]]", "1")],
    "Decode String": [('"3[a]2[bc]"', '"aaabcbc"'), ('"3[a2[c]]"', '"accaccacc"')],
    "Asteroid Collision": [("[5,10,-5]", "[5,10]"), ("[8,-8]", "[]")],
    "Daily Temperatures": [("[73,74,75,71,69,72,76,73]", "[1,1,4,2,1,1,0,0]")],
    "Koko Eating Bananas": [("[3,6,7,11], h = 8", "4")],
    "Search in Rotated Sorted Array": [("[4,5,6,7,0,1,2], target = 0", "4")],
    "Delete the Middle Node of a Linked List": [("[1,3,4,7,1,2,6]", "[1,3,4,1,2,6]")],
    "Odd Even Linked List": [("[1,2,3,4,5]", "[1,3,5,2,4]")],
    "Maximum Twin Sum of a Linked List": [("[5,4,2,1]", "6")],
    "LRU Cache": [("capacity = 2, operations = put(1,1), put(2,2), get(1), put(3,3), get(2)", "[1,-1]")],
    "Count Good Nodes in Binary Tree": [("[3,1,4,3,null,1,5]", "4")],
    "Path Sum III": [("[10,5,-3,3,2,null,11,3,-2,null,1], target = 8", "3")],
    "Lowest Common Ancestor of a Binary Tree": [("[3,5,1,6,2,0,8,null,null,7,4], p = 5, q = 1", "3")],
    "Binary Tree Right Side View": [("[1,2,3,null,5,null,4]", "[1,3,4]")],
    "Number of Provinces": [("[[1,1,0],[1,1,0],[0,0,1]]", "2")],
    "Rotting Oranges": [("[[2,1,1],[1,1,0],[0,1,1]]", "4")],
    "Course Schedule": [("numCourses = 2, prerequisites = [[1,0]]", "true")],
    "Kth Largest Element in an Array": [("[3,2,1,5,6,4], k = 2", "5")],
    "Letter Combinations of a Phone Number": [('"23"', '["ad","ae","af","bd","be","bf","cd","ce","cf"]')],
    "House Robber": [("[1,2,3,1]", "4"), ("[2,7,9,3,1]", "12")],
    "Unique Paths": [("m = 3, n = 7", "28")],
    "Longest Common Subsequence": [('"abcde", "ace"', "3")],
    "Implement Trie": [("insert apple, search apple, search app, startsWith app", "[true,false,true]")],
    "Non-overlapping Intervals": [("[[1,2],[2,3],[3,4],[1,3]]", "1")],
    "Online Stock Span": [("[100,80,60,70,60,75,85]", "[1,1,1,2,1,4,6]")],
    "Trapping Rain Water": [("[0,1,0,2,1,0,1,3,2,1,2,1]", "6")],
    "Minimum Window Substring": [('"ADOBECODEBANC", "ABC"', '"BANC"')],
    "Sliding Window Maximum": [("[1,3,-1,-3,5,3,6,7], k = 3", "[3,3,5,5,6,7]")],
    "Largest Rectangle in Histogram": [("[2,1,5,6,2,3]", "10")],
    "Edit Distance": [('"horse", "ros"', "3"), ('"intention", "execution"', "5")],
}

FUNCTION_SIGNATURES = {
    "Two Sum": [("int[]", "nums"), ("int", "target")],
    "Merge Strings Alternately": [("String", "word1"), ("String", "word2")],
    "Move Zeroes": [("int[]", "nums")],
    "Is Subsequence": [("String", "s"), ("String", "t")],
    "Find Pivot Index": [("int[]", "nums")],
    "Unique Number of Occurrences": [("int[]", "arr")],
    "Valid Parentheses": [("String", "s")],
    "Reverse Linked List": [("ListNode", "head")],
    "Maximum Depth of Binary Tree": [("TreeNode", "root")],
    "Counting Bits": [("int", "n")],
    "Product of Array Except Self": [("int[]", "nums")],
    "Group Anagrams": [("String[]", "strs")],
    "Longest Consecutive Sequence": [("int[]", "nums")],
    "String Compression": [("String", "chars")],
    "Container With Most Water": [("int[]", "height")],
    "Max Number of K-Sum Pairs": [("int[]", "nums"), ("int", "k")],
    "Longest Substring Without Repeating Characters": [("String", "s")],
    "Max Consecutive Ones III": [("int[]", "nums"), ("int", "k")],
    "Longest Subarray of 1s After Deleting One": [("int[]", "nums")],
    "Determine if Two Strings Are Close": [("String", "word1"), ("String", "word2")],
    "Equal Row and Column Pairs": [("int[][]", "grid")],
    "Decode String": [("String", "s")],
    "Asteroid Collision": [("int[]", "asteroids")],
    "Daily Temperatures": [("int[]", "temperatures")],
    "Koko Eating Bananas": [("int[]", "piles"), ("int", "h")],
    "Search in Rotated Sorted Array": [("int[]", "nums"), ("int", "target")],
    "Delete the Middle Node of a Linked List": [("ListNode", "head")],
    "Odd Even Linked List": [("ListNode", "head")],
    "Maximum Twin Sum of a Linked List": [("ListNode", "head")],
    "LRU Cache": [("int", "capacity"), ("String[]", "operations"), ("int[][]", "values")],
    "Count Good Nodes in Binary Tree": [("TreeNode", "root")],
    "Path Sum III": [("TreeNode", "root"), ("int", "targetSum")],
    "Lowest Common Ancestor of a Binary Tree": [("TreeNode", "root"), ("int", "p"), ("int", "q")],
    "Binary Tree Right Side View": [("TreeNode", "root")],
    "Number of Provinces": [("int[][]", "isConnected")],
    "Rotting Oranges": [("int[][]", "grid")],
    "Course Schedule": [("int", "numCourses"), ("int[][]", "prerequisites")],
    "Kth Largest Element in an Array": [("int[]", "nums"), ("int", "k")],
    "Letter Combinations of a Phone Number": [("String", "digits")],
    "House Robber": [("int[]", "nums")],
    "Unique Paths": [("int", "m"), ("int", "n")],
    "Longest Common Subsequence": [("String", "text1"), ("String", "text2")],
    "Implement Trie": [("String[]", "operations"), ("String[]", "words")],
    "Non-overlapping Intervals": [("int[][]", "intervals")],
    "Online Stock Span": [("int[]", "prices")],
    "Trapping Rain Water": [("int[]", "height")],
    "Minimum Window Substring": [("String", "s"), ("String", "t")],
    "Sliding Window Maximum": [("int[]", "nums"), ("int", "k")],
    "Largest Rectangle in Histogram": [("int[]", "heights")],
    "Edit Distance": [("String", "word1"), ("String", "word2")],
}

FUNCTION_CASES = {
    "Two Sum": [([[2, 7, 11, 15], 9], [0, 1]), ([[3, 2, 4], 6], [1, 2])],
    "Merge Strings Alternately": [(["abc", "pqr"], "apbqcr"), (["ab", "pqrs"], "apbqrs")],
    "Move Zeroes": [([[0, 1, 0, 3, 12]], [1, 3, 12, 0, 0]), ([[0, 0, 1]], [1, 0, 0])],
    "Is Subsequence": [(["abc", "ahbgdc"], True), (["axc", "ahbgdc"], False)],
    "Find Pivot Index": [([[1, 7, 3, 6, 5, 6]], 3), ([[1, 2, 3]], -1)],
    "Unique Number of Occurrences": [([[1, 2, 2, 1, 1, 3]], True), ([[1, 2]], False)],
    "Valid Parentheses": [[["()[]{}"], True], [["(]"], False]],
    "Reverse Linked List": [([[1, 2, 3, 4, 5]], [5, 4, 3, 2, 1]), ([[1, 2]], [2, 1])],
    "Maximum Depth of Binary Tree": [([[3, 9, 20, None, None, 15, 7]], 3), ([[1, None, 2]], 2)],
    "Counting Bits": [([5], [0, 1, 1, 2, 1, 2]), ([2], [0, 1, 1])],
    "Product of Array Except Self": [([[1, 2, 3, 4]], [24, 12, 8, 6]), ([[-1, 1, 0, -3, 3]], [0, 0, 9, 0, 0])],
    "Group Anagrams": [([["eat", "tea", "tan", "ate", "nat", "bat"]], [["ate", "eat", "tea"], ["bat"], ["nat", "tan"]])],
    "Longest Consecutive Sequence": [([[100, 4, 200, 1, 3, 2]], 4), ([[0, 3, 7, 2, 5, 8, 4, 6, 0, 1]], 9)],
    "String Compression": [(["aabbccc"], "a2b2c3"), (["abc"], "abc")],
    "Container With Most Water": [([[1, 8, 6, 2, 5, 4, 8, 3, 7]], 49), ([[1, 1]], 1)],
    "Max Number of K-Sum Pairs": [([[1, 2, 3, 4], 5], 2), ([[3, 1, 3, 4, 3], 6], 1)],
    "Longest Substring Without Repeating Characters": [(["abcabcbb"], 3), (["bbbbb"], 1)],
    "Max Consecutive Ones III": [([[1, 1, 1, 0, 0, 0, 1, 1, 1, 1, 0], 2], 6), ([[0, 0, 1, 1], 1], 3)],
    "Longest Subarray of 1s After Deleting One": [([[1, 1, 0, 1]], 3), ([[1, 1, 1]], 2)],
    "Determine if Two Strings Are Close": [(["abc", "bca"], True), (["a", "aa"], False)],
    "Equal Row and Column Pairs": [([[[3, 2, 1], [1, 7, 6], [2, 7, 7]]], 1), ([[[1, 2], [2, 1]]], 0)],
    "Decode String": [(["3[a]2[bc]"], "aaabcbc"), (["3[a2[c]]"], "accaccacc")],
    "Asteroid Collision": [([[5, 10, -5]], [5, 10]), ([[8, -8]], [])],
    "Daily Temperatures": [([[73, 74, 75, 71, 69, 72, 76, 73]], [1, 1, 4, 2, 1, 1, 0, 0]), ([[30, 40, 50, 60]], [1, 1, 1, 0])],
    "Koko Eating Bananas": [([[3, 6, 7, 11], 8], 4), ([[30, 11, 23, 4, 20], 5], 30)],
    "Search in Rotated Sorted Array": [([[4, 5, 6, 7, 0, 1, 2], 0], 4), ([[4, 5, 6, 7, 0, 1, 2], 3], -1)],
    "Delete the Middle Node of a Linked List": [([[1, 3, 4, 7, 1, 2, 6]], [1, 3, 4, 1, 2, 6]), ([[1, 2, 3, 4]], [1, 2, 4])],
    "Odd Even Linked List": [([[1, 2, 3, 4, 5]], [1, 3, 5, 2, 4]), ([[2, 1, 3, 5, 6, 4, 7]], [2, 3, 6, 7, 1, 5, 4])],
    "Maximum Twin Sum of a Linked List": [([[5, 4, 2, 1]], 6), ([[4, 2, 2, 3]], 7)],
    "LRU Cache": [([2, ["put", "put", "get", "put", "get"], [[1, 1], [2, 2], [1], [3, 3], [2]]], [1, -1])],
    "Count Good Nodes in Binary Tree": [([[3, 1, 4, 3, None, 1, 5]], 4), ([[3, 3, None, 4, 2]], 3)],
    "Path Sum III": [([[10, 5, -3, 3, 2, None, 11, 3, -2, None, 1], 8], 3), ([[5, 4, 8, 11, None, 13, 4, 7, 2, None, None, 5, 1], 22], 3)],
    "Lowest Common Ancestor of a Binary Tree": [([[3, 5, 1, 6, 2, 0, 8, None, None, 7, 4], 5, 1], 3), ([[3, 5, 1, 6, 2, 0, 8, None, None, 7, 4], 5, 4], 5)],
    "Binary Tree Right Side View": [([[1, 2, 3, None, 5, None, 4]], [1, 3, 4]), ([[1, None, 3]], [1, 3])],
    "Number of Provinces": [([[[1, 1, 0], [1, 1, 0], [0, 0, 1]]], 2), ([[[1, 0, 0], [0, 1, 0], [0, 0, 1]]], 3)],
    "Rotting Oranges": [([[[2, 1, 1], [1, 1, 0], [0, 1, 1]]], 4), ([[[2, 1, 1], [0, 1, 1], [1, 0, 1]]], -1)],
    "Course Schedule": [([2, [[1, 0]]], True), ([2, [[1, 0], [0, 1]]], False)],
    "Kth Largest Element in an Array": [([[3, 2, 1, 5, 6, 4], 2], 5), ([[3, 2, 3, 1, 2, 4, 5, 5, 6], 4], 4)],
    "Letter Combinations of a Phone Number": [(["23"], ["ad", "ae", "af", "bd", "be", "bf", "cd", "ce", "cf"]), ([""], [])],
    "House Robber": [([[1, 2, 3, 1]], 4), ([[2, 7, 9, 3, 1]], 12)],
    "Unique Paths": [([3, 7], 28), ([3, 2], 3)],
    "Longest Common Subsequence": [(["abcde", "ace"], 3), (["abc", "def"], 0)],
    "Implement Trie": [([["insert", "search", "search", "startsWith"], ["apple", "apple", "app", "app"]], [True, False, True])],
    "Non-overlapping Intervals": [([[[1, 2], [2, 3], [3, 4], [1, 3]]], 1), ([[[1, 2], [1, 2], [1, 2]]], 2)],
    "Online Stock Span": [([[100, 80, 60, 70, 60, 75, 85]], [1, 1, 1, 2, 1, 4, 6])],
    "Trapping Rain Water": [([[0, 1, 0, 2, 1, 0, 1, 3, 2, 1, 2, 1]], 6), ([[4, 2, 0, 3, 2, 5]], 9)],
    "Minimum Window Substring": [(["ADOBECODEBANC", "ABC"], "BANC"), (["a", "aa"], "")],
    "Sliding Window Maximum": [([[1, 3, -1, -3, 5, 3, 6, 7], 3], [3, 3, 5, 5, 6, 7]), ([[1], 1], [1])],
    "Largest Rectangle in Histogram": [([[2, 1, 5, 6, 2, 3]], 10), ([[2, 4]], 4)],
    "Edit Distance": [(["horse", "ros"], 3), (["intention", "execution"], 5)],
}

FUNCTION_CASES.update(NODE_CASES)
FUNCTION_CASES.update(UNORDERED_CASES)


def function_signature_text(title):
    params = ", ".join(name for _, name in FUNCTION_SIGNATURES[title])
    return f"solve({params})"


def build_python_starter(title):
    params = ", ".join(name for _, name in FUNCTION_SIGNATURES[title])
    if title in NODE_TITLES:
        return build_node_python_starter(title, params)
    return f"def solve({params}):\n    # Write your solution here.\n    pass\n"


def build_java_starter(title):
    params = ", ".join(f"{java_type} {name}" for java_type, name in FUNCTION_SIGNATURES[title])
    if title in NODE_TITLES:
        return build_node_java_starter(title, params)
    return "import java.util.*;\n\nclass Solution {\n    public Object solve(" + params + ") {\n        // Write your solution here.\n        return null;\n    }\n}\n"


def build_description(title, difficulty, tag_slugs):
    examples = SAMPLE_CASES.get(title, [])
    example_text = "\n\n".join(
        f"Example {index}:\nInput: {input_text}\nOutput: {output_text}"
        for index, (input_text, output_text) in enumerate(examples, start=1)
    )
    node_input_note = ""
    if title in NODE_TITLES:
        structure = "linked list" if title in LINKED_LIST_TITLES else "binary tree"
        node_input_note = (
            f" The platform constructs the {structure} from the value/level-order array shown in each test case."
            " Implement the node-based function signature directly; do not parse the array yourself."
        )
    output_order_note = OUTPUT_ORDER_NOTES.get(title, "")
    if output_order_note:
        output_order_note = f"\n\n## Output Ordering\n\n{output_order_note}"
    return (
        f"## {title}\n\n"
        f"{PROBLEM_BRIEFS[title]}\n\n"
        f"Function signature:\n`{function_signature_text(title)}`\n\n"
        f"Write a solution that handles the sample cases and hidden edge cases efficiently.{node_input_note}\n\n"
        f"{example_text}{output_order_note}\n\n"
        "## Constraints\n\n"
        "- Input sizes are chosen to require the intended data-structure or algorithmic pattern.\n"
        "- Values fit within standard 32-bit signed integer ranges unless the statement implies strings or collections.\n"
        f"- Target difficulty: {difficulty.title()}.\n"
        f"- Focus tags: {', '.join(tag_slugs)}.\n\n"
        "## Expected Approach\n\n"
        "Use the listed tags as the primary hint. Aim for the usual interview-grade time complexity for this pattern, "
        "and avoid brute force when a hash map, stack, two-pointer scan, heap, graph traversal, or dynamic-programming "
        "state gives a better bound."
    )


def build_reference_solution(title, language):
    if title in NODE_TITLES:
        return build_node_python_reference(title) if language == "python" else build_node_java_reference(title)
    if title in UNORDERED_COMPARISON_MODES:
        return UNORDERED_PYTHON_SOLUTIONS[title] if language == "python" else UNORDERED_JAVA_SOLUTIONS[title]
    comment = "#" if language == "python" else "//"
    return (
        f"{comment} Reference solution for {title}\n"
        f"{comment} Use the canonical interview approach suggested by the problem tags.\n"
        f"{comment} Keep the implementation focused on the expected complexity: hash lookups for frequency/index work,\n"
        f"{comment} two pointers or sliding windows for contiguous ranges, stacks for nearest-greater/parser states,\n"
        f"{comment} BFS/DFS for graph and tree reachability, heaps for repeated best-choice extraction, and DP for\n"
        f"{comment} overlapping subproblems. Validate against the sample and hidden test cases seeded with this problem.\n"
    )


class Command(BaseCommand):
    help = "Seed the curated 50-problem interview preparation track and tags."

    def add_arguments(self, parser):
        parser.add_argument(
            "--create-missing",
            action="store_true",
            help="Create active question records for problems that are not already present.",
        )

    def handle(self, *args, **options):
        create_missing = options["create_missing"]
        missing = []
        created_questions = 0
        linked_questions = 0

        with transaction.atomic():
            tags = {}
            for _, _, _, tag_slugs in PROBLEMS:
                for tag_slug in tag_slugs:
                    tag, _ = Tag.objects.get_or_create(slug=tag_slug, defaults={"name": tag_slug.replace("-", " ").title()})
                    tags[tag_slug] = tag

            track, _ = Track.objects.update_or_create(slug=TRACK["slug"], defaults=TRACK)
            sections = {}
            for order, section_title in enumerate(dict.fromkeys(problem[0] for problem in PROBLEMS), start=1):
                section, _ = TrackSection.objects.update_or_create(
                    track=track,
                    title=section_title,
                    defaults={
                        "description": SECTION_DESCRIPTIONS.get(section_title, ""),
                        "order": order,
                    },
                )
                sections[section_title] = section

            for order, (section_title, title, difficulty, tag_slugs) in enumerate(PROBLEMS, start=1):
                slug = slugify(title)
                question = Question.objects.filter(slug=slug).first()
                question_defaults = {
                    "title": title,
                    "difficulty": difficulty,
                    "description": build_description(title, difficulty, tag_slugs),
                    "starter_code": build_java_starter(title),
                    "java_starter_code": build_java_starter(title),
                    "python_starter_code": build_python_starter(title),
                    "java_reference_solution": build_reference_solution(title, "java"),
                    "python_reference_solution": build_reference_solution(title, "python"),
                    "execution_mode": Question.ExecutionMode.FUNCTION,
                    "function_name": "solve",
                    "comparison_mode": UNORDERED_COMPARISON_MODES.get(title, Question.ComparisonMode.ORDERED),
                    "is_active": True,
                }
                if question is None and create_missing:
                    question = Question.objects.create(
                        slug=slug,
                        **question_defaults,
                    )
                    created_questions += 1
                if question is None:
                    missing.append(title)
                    continue
                if create_missing:
                    update_fields = []
                    for field, value in question_defaults.items():
                        if getattr(question, field) != value:
                            setattr(question, field, value)
                            update_fields.append(field)
                    if update_fields:
                        question.save(update_fields=update_fields)

                question.tags.add(*(tags[tag_slug] for tag_slug in tag_slugs))
                if create_missing:
                    expected_case_names = set()
                    for case_order, (function_args, expected_value) in enumerate(FUNCTION_CASES.get(title, []), start=1):
                        is_sample = case_order <= 2
                        case_name = f"Sample {case_order}" if is_sample else f"Hidden {case_order - 2}"
                        expected_case_names.add(case_name)
                        TestCase.objects.update_or_create(
                            question=question,
                            name=case_name,
                            defaults={
                                "stdin": "",
                                "function_args": function_args,
                                "expected_value": expected_value,
                                "expected_output": json.dumps(expected_value, separators=(",", ":")),
                                "is_sample": is_sample,
                                "is_hidden": not is_sample,
                                "order": case_order,
                            },
                        )
                    if title in NODE_TITLES or title in UNORDERED_COMPARISON_MODES:
                        question.test_cases.exclude(name__in=expected_case_names).delete()
                section = sections[section_title]
                TrackQuestion.objects.update_or_create(
                    section=section,
                    question=question,
                    defaults={
                        "order": order,
                        "is_required": True,
                        "recommended_time_minutes": {"easy": 20, "medium": 35, "hard": 50}[difficulty],
                    },
                )
                linked_questions += 1

        self.stdout.write(self.style.SUCCESS(f"Interview track ready. Linked {linked_questions} questions. Created {created_questions} question shells."))
        if missing:
            self.stdout.write(self.style.WARNING(f"Missing {len(missing)} questions. Re-run with --create-missing to create shells:"))
            for title in missing:
                self.stdout.write(f" - {title}")

"""Curated definitions for node-based questions in the interview track."""

LINKED_LIST_TITLES = {
    "Reverse Linked List",
    "Delete the Middle Node of a Linked List",
    "Odd Even Linked List",
    "Maximum Twin Sum of a Linked List",
}

TREE_TITLES = {
    "Maximum Depth of Binary Tree",
    "Count Good Nodes in Binary Tree",
    "Path Sum III",
    "Lowest Common Ancestor of a Binary Tree",
    "Binary Tree Right Side View",
}

NODE_TITLES = LINKED_LIST_TITLES | TREE_TITLES

JAVA_RETURN_TYPES = {
    "Reverse Linked List": "ListNode",
    "Delete the Middle Node of a Linked List": "ListNode",
    "Odd Even Linked List": "ListNode",
    "Maximum Twin Sum of a Linked List": "int",
    "Maximum Depth of Binary Tree": "int",
    "Count Good Nodes in Binary Tree": "int",
    "Path Sum III": "int",
    "Lowest Common Ancestor of a Binary Tree": "TreeNode",
    "Binary Tree Right Side View": "List<Integer>",
}

JAVA_LIST_NODE = """class ListNode {
    int val;
    ListNode next;

    ListNode() {}
    ListNode(int val) { this.val = val; }
    ListNode(int val, ListNode next) { this.val = val; this.next = next; }
}
"""

JAVA_TREE_NODE = """class TreeNode {
    int val;
    TreeNode left;
    TreeNode right;

    TreeNode() {}
    TreeNode(int val) { this.val = val; }
    TreeNode(int val, TreeNode left, TreeNode right) {
        this.val = val;
        this.left = left;
        this.right = right;
    }
}
"""

PYTHON_LIST_NODE = """class ListNode:
    def __init__(self, val=0, next=None):
        self.val = val
        self.next = next
"""

PYTHON_TREE_NODE = """class TreeNode:
    def __init__(self, val=0, left=None, right=None):
        self.val = val
        self.left = left
        self.right = right
"""

JAVA_SOLUTIONS = {
    "Reverse Linked List": """class Solution {
    public ListNode solve(ListNode head) {
        ListNode previous = null;
        while (head != null) {
            ListNode next = head.next;
            head.next = previous;
            previous = head;
            head = next;
        }
        return previous;
    }
}
""",
    "Delete the Middle Node of a Linked List": """class Solution {
    public ListNode solve(ListNode head) {
        if (head == null || head.next == null) return null;
        ListNode slow = head;
        ListNode fast = head.next.next;
        while (fast != null && fast.next != null) {
            slow = slow.next;
            fast = fast.next.next;
        }
        slow.next = slow.next.next;
        return head;
    }
}
""",
    "Odd Even Linked List": """class Solution {
    public ListNode solve(ListNode head) {
        if (head == null) return null;
        ListNode odd = head;
        ListNode even = head.next;
        ListNode evenHead = even;
        while (even != null && even.next != null) {
            odd.next = even.next;
            odd = odd.next;
            even.next = odd.next;
            even = even.next;
        }
        odd.next = evenHead;
        return head;
    }
}
""",
    "Maximum Twin Sum of a Linked List": """class Solution {
    public int solve(ListNode head) {
        ListNode slow = head;
        ListNode fast = head;
        while (fast != null && fast.next != null) {
            slow = slow.next;
            fast = fast.next.next;
        }
        ListNode reversed = null;
        while (slow != null) {
            ListNode next = slow.next;
            slow.next = reversed;
            reversed = slow;
            slow = next;
        }
        int answer = Integer.MIN_VALUE;
        while (reversed != null) {
            answer = Math.max(answer, head.val + reversed.val);
            head = head.next;
            reversed = reversed.next;
        }
        return answer;
    }
}
""",
    "Maximum Depth of Binary Tree": """class Solution {
    public int solve(TreeNode root) {
        if (root == null) return 0;
        return 1 + Math.max(solve(root.left), solve(root.right));
    }
}
""",
    "Count Good Nodes in Binary Tree": """class Solution {
    public int solve(TreeNode root) {
        return count(root, Integer.MIN_VALUE);
    }

    private int count(TreeNode node, int maximum) {
        if (node == null) return 0;
        int good = node.val >= maximum ? 1 : 0;
        int nextMaximum = Math.max(maximum, node.val);
        return good + count(node.left, nextMaximum) + count(node.right, nextMaximum);
    }
}
""",
    "Path Sum III": """import java.util.*;

class Solution {
    public int solve(TreeNode root, int targetSum) {
        Map<Long, Integer> prefixes = new HashMap<>();
        prefixes.put(0L, 1);
        return count(root, 0L, targetSum, prefixes);
    }

    private int count(TreeNode node, long sum, int target, Map<Long, Integer> prefixes) {
        if (node == null) return 0;
        sum += node.val;
        int result = prefixes.getOrDefault(sum - target, 0);
        prefixes.put(sum, prefixes.getOrDefault(sum, 0) + 1);
        result += count(node.left, sum, target, prefixes);
        result += count(node.right, sum, target, prefixes);
        prefixes.put(sum, prefixes.get(sum) - 1);
        return result;
    }
}
""",
    "Lowest Common Ancestor of a Binary Tree": """class Solution {
    public TreeNode solve(TreeNode root, int p, int q) {
        if (root == null || root.val == p || root.val == q) return root;
        TreeNode left = solve(root.left, p, q);
        TreeNode right = solve(root.right, p, q);
        if (left != null && right != null) return root;
        return left != null ? left : right;
    }
}
""",
    "Binary Tree Right Side View": """import java.util.*;

class Solution {
    public List<Integer> solve(TreeNode root) {
        List<Integer> result = new ArrayList<>();
        if (root == null) return result;
        Queue<TreeNode> queue = new ArrayDeque<>();
        queue.add(root);
        while (!queue.isEmpty()) {
            int levelSize = queue.size();
            for (int i = 0; i < levelSize; i++) {
                TreeNode node = queue.remove();
                if (i == levelSize - 1) result.add(node.val);
                if (node.left != null) queue.add(node.left);
                if (node.right != null) queue.add(node.right);
            }
        }
        return result;
    }
}
""",
}

PYTHON_SOLUTIONS = {
    "Reverse Linked List": """def solve(head):
    previous = None
    while head:
        next_node = head.next
        head.next = previous
        previous = head
        head = next_node
    return previous
""",
    "Delete the Middle Node of a Linked List": """def solve(head):
    if not head or not head.next:
        return None
    slow = head
    fast = head.next.next
    while fast and fast.next:
        slow = slow.next
        fast = fast.next.next
    slow.next = slow.next.next
    return head
""",
    "Odd Even Linked List": """def solve(head):
    if not head:
        return None
    odd = head
    even = head.next
    even_head = even
    while even and even.next:
        odd.next = even.next
        odd = odd.next
        even.next = odd.next
        even = even.next
    odd.next = even_head
    return head
""",
    "Maximum Twin Sum of a Linked List": """def solve(head):
    slow = fast = head
    while fast and fast.next:
        slow = slow.next
        fast = fast.next.next
    reversed_head = None
    while slow:
        next_node = slow.next
        slow.next = reversed_head
        reversed_head = slow
        slow = next_node
    answer = float('-inf')
    while reversed_head:
        answer = max(answer, head.val + reversed_head.val)
        head = head.next
        reversed_head = reversed_head.next
    return answer
""",
    "Maximum Depth of Binary Tree": """def solve(root):
    if not root:
        return 0
    return 1 + max(solve(root.left), solve(root.right))
""",
    "Count Good Nodes in Binary Tree": """def solve(root):
    def count(node, maximum):
        if not node:
            return 0
        good = int(node.val >= maximum)
        maximum = max(maximum, node.val)
        return good + count(node.left, maximum) + count(node.right, maximum)
    return count(root, float('-inf'))
""",
    "Path Sum III": """def solve(root, targetSum):
    prefixes = {0: 1}
    def count(node, total):
        if not node:
            return 0
        total += node.val
        result = prefixes.get(total - targetSum, 0)
        prefixes[total] = prefixes.get(total, 0) + 1
        result += count(node.left, total) + count(node.right, total)
        prefixes[total] -= 1
        return result
    return count(root, 0)
""",
    "Lowest Common Ancestor of a Binary Tree": """def solve(root, p, q):
    if not root or root.val == p or root.val == q:
        return root
    left = solve(root.left, p, q)
    right = solve(root.right, p, q)
    if left and right:
        return root
    return left or right
""",
    "Binary Tree Right Side View": """def solve(root):
    if not root:
        return []
    result = []
    queue = [root]
    while queue:
        result.append(queue[-1].val)
        next_level = []
        for node in queue:
            if node.left:
                next_level.append(node.left)
            if node.right:
                next_level.append(node.right)
        queue = next_level
    return result
""",
}

NODE_CASES = {
    "Reverse Linked List": [
        ([[1, 2, 3, 4, 5]], [5, 4, 3, 2, 1]), ([[1, 2]], [2, 1]),
        ([[]], []), ([[1]], [1]), ([[-3, 0, 7]], [7, 0, -3]),
        ([[1, 1, 2]], [2, 1, 1]), ([[0, 1, 2, 3, 4, 5, 6, 7, 8, 9]], [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]),
        ([[-1, -2]], [-2, -1]), ([[0]], [0]), ([[5, 4, 3, 2, 1, 0]], [0, 1, 2, 3, 4, 5]),
    ],
    "Delete the Middle Node of a Linked List": [
        ([[1, 3, 4, 7, 1, 2, 6]], [1, 3, 4, 1, 2, 6]), ([[1, 2, 3, 4]], [1, 2, 4]),
        ([[1]], []), ([[1, 2]], [1]), ([[1, 2, 3]], [1, 3]), ([[2, 1, 3, 5, 6]], [2, 1, 5, 6]),
        ([[0, 0, 0]], [0, 0]), ([[-3, -2, -1, 0, 1, 2]], [-3, -2, -1, 1, 2]),
        ([[9, 8, 7, 6, 5, 4, 3, 2]], [9, 8, 7, 6, 4, 3, 2]), ([[5, 5]], [5]),
    ],
    "Odd Even Linked List": [
        ([[1, 2, 3, 4, 5]], [1, 3, 5, 2, 4]), ([[2, 1, 3, 5, 6, 4, 7]], [2, 3, 6, 7, 1, 5, 4]),
        ([[]], []), ([[1]], [1]), ([[1, 2]], [1, 2]), ([[1, 2, 3]], [1, 3, 2]),
        ([[1, 2, 3, 4]], [1, 3, 2, 4]), ([[0, 0, 1, 1]], [0, 1, 0, 1]),
        ([[-1, -2, -3, -4, -5, -6]], [-1, -3, -5, -2, -4, -6]), ([[9, 8, 7, 6, 5, 4, 3, 2]], [9, 7, 5, 3, 8, 6, 4, 2]),
    ],
    "Maximum Twin Sum of a Linked List": [
        ([[5, 4, 2, 1]], 6), ([[4, 2, 2, 3]], 7), ([[1, 2]], 3), ([[1, 100, 2, 3]], 102),
        ([[1, 2, 3, 4, 5, 6]], 7), ([[9, 9]], 18), ([[0, 0, 0, 0]], 0),
        ([[-5, -2, -3, -4]], -5), ([[10, 1, 1, 10]], 20), ([[1, 8, 3, 4, 5, 6, 7, 2]], 15),
    ],
    "Maximum Depth of Binary Tree": [
        ([[3, 9, 20, None, None, 15, 7]], 3), ([[1, None, 2]], 2), ([[]], 0), ([[1]], 1),
        ([[1, 2, None, 3, None, 4]], 4), ([[1, None, 2, None, 3, None, 4]], 4),
        ([[1, 2, 3, 4, 5, 6, 7]], 3), ([[-1, -2, -3, None, -4]], 3),
        ([[0, 0, 0, 0, None, None, 0]], 3), ([[1, 2, 3, None, 4, None, 5, 6]], 4),
    ],
    "Count Good Nodes in Binary Tree": [
        ([[3, 1, 4, 3, None, 1, 5]], 4), ([[3, 3, None, 4, 2]], 3), ([[]], 0), ([[1]], 1),
        ([[1, 2, 3]], 3), ([[5, 4, 3, 2, None, None, 1]], 1), ([[-1, -2, -3]], 1),
        ([[-3, -3, -2, -4, None, -2, -1]], 5), ([[0, 0, 0, 0, 0]], 5),
        ([[2, 1, 5, 0, 3, 4, 6]], 4),
    ],
    "Path Sum III": [
        ([[10, 5, -3, 3, 2, None, 11, 3, -2, None, 1], 8], 3),
        ([[5, 4, 8, 11, None, 13, 4, 7, 2, None, None, 5, 1], 22], 3),
        ([[], 0], 0), ([[1], 1], 1), ([[1], 0], 0), ([[1, -1, -1, 1, 0, -1, 1], 0], 6),
        ([[0, 0, 0], 0], 5), ([[-2, None, -3], -5], 1), ([[1, 2, 3], 3], 2),
        ([[1000000000, 1000000000, None, 1000000000], 2000000000], 2),
    ],
    "Lowest Common Ancestor of a Binary Tree": [
        ([[3, 5, 1, 6, 2, 0, 8, None, None, 7, 4], 5, 1], 3),
        ([[3, 5, 1, 6, 2, 0, 8, None, None, 7, 4], 5, 4], 5),
        ([[1, 2], 1, 2], 1), ([[1, 2, 3], 2, 3], 1), ([[1, 2, None, 3, None, 4], 3, 4], 3),
        ([[1, None, 2, 3, 4], 3, 4], 2), ([[-1, -2, -3], -2, -3], -1),
        ([[10, 5, 15, 2, 7, 12, 20], 2, 7], 5), ([[10, 5, 15, 2, 7, 12, 20], 2, 20], 10),
        ([[0, -3, 9, -10, None, 5], -10, 5], 0),
    ],
    "Binary Tree Right Side View": [
        ([[1, 2, 3, None, 5, None, 4]], [1, 3, 4]), ([[1, None, 3]], [1, 3]), ([[]], []),
        ([[1]], [1]), ([[1, 2, None, 3]], [1, 2, 3]), ([[1, None, 2, 3]], [1, 2, 3]),
        ([[1, 2, 3, 4, 5, 6, 7]], [1, 3, 7]), ([[-1, -2, -3, None, -4]], [-1, -3, -4]),
        ([[0, 0, 0, 0, None, None, 0]], [0, 0, 0]), ([[1, 2, 3, None, 5, 6, None, 7]], [1, 3, 6, 7]),
    ],
}


def build_java_starter(title, params):
    node_definition = JAVA_LIST_NODE if title in LINKED_LIST_TITLES else JAVA_TREE_NODE
    return_type = JAVA_RETURN_TYPES[title]
    return (
        "import java.util.*;\n\n"
        f"{node_definition}\n"
        "class Solution {\n"
        f"    public {return_type} solve({params}) {{\n"
        "        // Write your solution here.\n"
        "        return " + ("0" if return_type == "int" else "null") + ";\n"
        "    }\n"
        "}\n"
    )


def build_python_starter(title, params):
    node_definition = PYTHON_LIST_NODE if title in LINKED_LIST_TITLES else PYTHON_TREE_NODE
    return f"{node_definition}\n\ndef solve({params}):\n    # Write your solution here.\n    pass\n"


def build_java_reference(title):
    node_definition = JAVA_LIST_NODE if title in LINKED_LIST_TITLES else JAVA_TREE_NODE
    return "import java.util.*;\n\n" + node_definition + "\n" + JAVA_SOLUTIONS[title].replace("import java.util.*;\n\n", "")


def build_python_reference(title):
    node_definition = PYTHON_LIST_NODE if title in LINKED_LIST_TITLES else PYTHON_TREE_NODE
    return node_definition + "\n\n" + PYTHON_SOLUTIONS[title]

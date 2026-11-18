import { expect, test } from "@playwright/test";
import type { RevisionSubmission } from "../lib/api";
import { addRevisionTags, filterRevisionByTag, getRevisionTagOptions } from "../lib/trackRevision";

const lists = { id: 1, slug: "lists", name: "Linked Lists" };
const arrays = { id: 2, slug: "arrays", name: "Arrays" };

function submission(id: number, slug: string): RevisionSubmission {
  return {
    id,
    question_slug: slug,
    question_title: slug,
    language: "python",
    code: "return result",
    execution_time_ms: 1,
    memory_kb: 1,
    created_at: "2026-01-01T00:00:00Z",
  };
}

test("joins tags across sections and retains submissions missing from the track", () => {
  const items = addRevisionTags(
    [submission(1, "reverse"), submission(2, "removed"), submission(3, "merge")],
    [
      { questions: [{ slug: "merge", tags: [arrays, lists] }] },
      { questions: [{ slug: "reverse", tags: [lists] }] },
    ],
  );

  expect(items.map(({ id, tags }) => [id, tags])).toEqual([
    [1, [lists]],
    [2, []],
    [3, [arrays, lists]],
  ]);
  expect(getRevisionTagOptions(items)).toEqual([["arrays", "Arrays"], ["lists", "Linked Lists"]]);
  expect(filterRevisionByTag(items, "lists").map(({ id }) => id)).toEqual([1, 3]);
  expect(filterRevisionByTag(items, "all")).toEqual(items);
  expect(filterRevisionByTag(items, "unknown")).toEqual([]);
});

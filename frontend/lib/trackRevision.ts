import type { RevisionSubmission, Tag, TrackQuestion } from "@/lib/api";

export type TrackRevisionSubmission = RevisionSubmission & { tags: Tag[] };

export function addRevisionTags(
  submissions: RevisionSubmission[],
  sections: { questions: Pick<TrackQuestion, "slug" | "tags">[] }[],
): TrackRevisionSubmission[] {
  const tagsByQuestion = new Map(
    sections.flatMap((section) => section.questions).map((question) => [question.slug, question.tags] as const),
  );
  return submissions.map((submission) => ({
    ...submission,
    tags: tagsByQuestion.get(submission.question_slug) ?? [],
  }));
}

export function getRevisionTagOptions(items: TrackRevisionSubmission[]) {
  const tags = new Map<string, string>();
  items.forEach((item) => item.tags.forEach((tag) => tags.set(tag.slug, tag.name)));
  return Array.from(tags.entries()).sort((left, right) => left[1].localeCompare(right[1]));
}

export function filterRevisionByTag(items: TrackRevisionSubmission[], tag: string) {
  return tag === "all" ? items : items.filter((item) => item.tags.some((itemTag) => itemTag.slug === tag));
}

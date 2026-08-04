export const INTERVIEW_PREPARATION_TRACK = "interview-preparation";

export type TrackContext = {
  slug: typeof INTERVIEW_PREPARATION_TRACK;
  tag: string | null;
};

export function getTrackContext(searchParams: { get(name: string): string | null }) {
  if (searchParams.get("from") !== INTERVIEW_PREPARATION_TRACK) {
    return null;
  }

  return {
    slug: INTERVIEW_PREPARATION_TRACK,
    tag: normalizedTag(searchParams.get("tag")),
  } satisfies TrackContext;
}

export function withTrackContext(path: string, trackContext?: TrackContext | null) {
  if (!trackContext) {
    return path;
  }

  const separator = path.includes("?") ? "&" : "?";
  const params = new URLSearchParams({ from: trackContext.slug });
  if (trackContext.tag) {
    params.set("tag", trackContext.tag);
  }
  return `${path}${separator}${params.toString()}`;
}

export function trackReturnPath(trackContext: TrackContext) {
  const tagQuery = trackContext.tag ? `?tag=${encodeURIComponent(trackContext.tag)}` : "";
  return `/tracks/${trackContext.slug}${tagQuery}`;
}

export function normalizedTag(tag: string | null) {
  return tag?.trim() && tag !== "all" ? tag.trim() : null;
}

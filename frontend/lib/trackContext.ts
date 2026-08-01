export const INTERVIEW_PREPARATION_TRACK = "interview-preparation";

export function getTrackContext(searchParams: { get(name: string): string | null }) {
  return searchParams.get("from") === INTERVIEW_PREPARATION_TRACK ? INTERVIEW_PREPARATION_TRACK : null;
}

export function withTrackContext(path: string, trackSlug?: string | null) {
  if (trackSlug !== INTERVIEW_PREPARATION_TRACK) {
    return path;
  }

  const separator = path.includes("?") ? "&" : "?";
  return `${path}${separator}from=${INTERVIEW_PREPARATION_TRACK}`;
}

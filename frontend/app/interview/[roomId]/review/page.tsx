"use client";

import { AuthGate } from "@/components/AuthGate";
import { InterviewRoomWorkspace } from "@/components/InterviewRoomWorkspace";

export default function InterviewReviewPage({ params }: { params: { roomId: string } }) {
  return <AuthGate>{() => <InterviewRoomWorkspace roomId={params.roomId} />}</AuthGate>;
}

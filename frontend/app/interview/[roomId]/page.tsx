"use client";

import { InterviewRoomWorkspace } from "@/components/InterviewRoomWorkspace";

export default function InterviewRoomPage({ params }: { params: { roomId: string } }) {
  return <InterviewRoomWorkspace roomId={params.roomId} />;
}

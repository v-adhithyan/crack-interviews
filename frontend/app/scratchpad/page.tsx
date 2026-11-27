"use client";

import { AuthGate } from "@/components/AuthGate";
import { Scratchpad } from "@/components/Scratchpad";

export default function ScratchpadPage() {
  return <AuthGate>{() => <Scratchpad />}</AuthGate>;
}

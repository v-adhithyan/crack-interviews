export const dynamic = "force-dynamic";

export function GET() {
  return Response.json(
    { status: "ok" },
    {
      headers: {
        "Access-Control-Allow-Origin": "*",
        "Cache-Control": "no-store",
      },
    },
  );
}

import { CodeWorkspace } from "@/components/CodeWorkspace";
import { getQuestion } from "@/lib/api";

export default async function QuestionPage({ params }: { params: { slug: string } }) {
  const question = await getQuestion(params.slug);

  return <CodeWorkspace question={question} />;
}

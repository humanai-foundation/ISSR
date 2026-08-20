import { MatchForm } from "@/components/match/match-form";
import { Topbar } from "@/components/layout/topbar";

export default function MatchPage() {
  return (
    <>
      <Topbar>
        <h1 className="font-heading text-lg font-semibold">AI Match</h1>
      </Topbar>
      <main className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-3xl">
          <p className="mb-6 text-sm text-muted-foreground">
            Paste a researcher profile, abstract, or project idea to find relevant grants. Ranking
            combines vector similarity with ontology tag overlap, and the top results get a
            plain-language AI explanation of why they matched.
          </p>
          <MatchForm />
        </div>
      </main>
    </>
  );
}

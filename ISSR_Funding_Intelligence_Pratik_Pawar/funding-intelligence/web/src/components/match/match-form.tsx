"use client";

import { Info, Loader2, WandSparkles, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { MatchResultCard } from "@/components/match/match-result-card";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api/client";
import { streamMatchProfile } from "@/lib/api/match";
import type { MatchResult } from "@/lib/types";

const MIN_LENGTH = 10;
const MAX_LENGTH = 5000;
// No server-enforced timeout exists (matching/explain.py's own doc comment:
// sequential LLM calls, ~8s each, 5 by default -> 30-45s typical, ~100s
// worst case if every one times out). 120s gives headroom above the
// documented worst case rather than guessing at a round number.
const CLIENT_TIMEOUT_MS = 120_000;

// A match run is expensive (up to ~100s, sequential local-LLM calls) --
// clicking into a result to read the full FOA and coming back should not
// throw that work away. sessionStorage (not localStorage): results should
// survive in-tab navigation but not linger stale across days as the corpus
// changes underneath them. Persisted keyed together so a corrupt/partial
// write can never restore results without their originating profile text.
const STORAGE_KEY = "issr-match-state-v1";

interface StoredMatchState {
  profileText: string;
  results: MatchResult[];
  llmAvailable: boolean;
}

function loadStoredState(): StoredMatchState | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as StoredMatchState;
    if (!parsed.profileText || !Array.isArray(parsed.results)) return null;
    return parsed;
  } catch {
    return null;
  }
}

// "ranking": submitted, no results yet. "explaining": the ranked list has
// arrived and is rendered -- remaining work is per-card AI explanations
// filling in progressively, tracked via explainedCount/explainWindowSize
// below rather than a guessed timer, now that the stream gives real
// progress instead of one atomic response to wait on blindly.
type Phase = "idle" | "ranking" | "explaining" | "done" | "error";

export function MatchForm() {
  // Lazy initializer: reads sessionStorage once, on mount, not on every
  // render -- the other useState calls below just read off this already-
  // resolved value.
  const [restored] = useState(loadStoredState);
  const [profileText, setProfileText] = useState(restored?.profileText ?? "");
  const [phase, setPhase] = useState<Phase>(restored ? "done" : "idle");
  const [results, setResults] = useState<MatchResult[]>(restored?.results ?? []);
  const [explainWindowSize, setExplainWindowSize] = useState(0);
  const [explainedFoaIds, setExplainedFoaIds] = useState<Set<string>>(new Set());
  const [llmAvailable, setLlmAvailable] = useState(restored?.llmAvailable ?? true);
  const [errorMessage, setErrorMessage] = useState("");

  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => abortRef.current?.abort();
  }, []);

  const trimmedLength = profileText.trim().length;
  const tooShort = trimmedLength > 0 && trimmedLength < MIN_LENGTH;
  const loading = phase === "ranking" || phase === "explaining";

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (trimmedLength < MIN_LENGTH || loading) return;

    const controller = new AbortController();
    abortRef.current = controller;
    const timeoutId = setTimeout(() => controller.abort(), CLIENT_TIMEOUT_MS);

    setPhase("ranking");
    setErrorMessage("");
    setResults([]);
    setExplainWindowSize(0);
    setExplainedFoaIds(new Set());

    let finalResults: MatchResult[] = [];
    let finalLlmAvailable = false;

    try {
      for await (const event of streamMatchProfile({ profileText, signal: controller.signal })) {
        switch (event.type) {
          case "ranked":
            finalResults = event.items;
            setResults(event.items);
            setExplainWindowSize(event.explain_window_size);
            setPhase(event.explain_window_size > 0 ? "explaining" : "done");
            break;

          case "explanation":
            setResults((prev) =>
              prev.map((r) =>
                r.foa_id === event.foa_id
                  ? { ...r, match_explanation: event.match_explanation, llm_relevance: event.llm_relevance }
                  : r,
              ),
            );
            setExplainedFoaIds((prev) => new Set(prev).add(event.foa_id));
            break;

          case "reorder": {
            const order = event.foa_ids;
            setResults((prev) => {
              const byId = new Map(prev.map((r) => [r.foa_id, r]));
              const windowSorted = order.map((id) => byId.get(id)).filter((r): r is MatchResult => !!r);
              const rest = prev.filter((r) => !order.includes(r.foa_id));
              const next = [...windowSorted, ...rest];
              finalResults = next;
              return next;
            });
            break;
          }

          case "done":
            finalLlmAvailable = event.llm_available;
            setLlmAvailable(event.llm_available);
            setPhase("done");
            break;
        }
      }

      try {
        const toStore: StoredMatchState = {
          profileText,
          results: finalResults,
          llmAvailable: finalLlmAvailable,
        };
        window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(toStore));
      } catch {
        // Storage can fail (private browsing, quota) -- the run itself
        // already succeeded and is on screen, so this is a lost convenience,
        // not a lost result. Nothing to surface to the user.
      }
    } catch (err) {
      if (controller.signal.aborted) {
        setErrorMessage(
          err instanceof DOMException && err.name === "AbortError"
            ? "Cancelled."
            : "Timed out. The matcher may be under heavy load -- try again.",
        );
      } else if (err instanceof ApiError) {
        setErrorMessage(`Match failed (${err.status}): ${err.message}`);
      } else {
        setErrorMessage("Match failed. Is the API server running?");
      }
      setPhase("error");
    } finally {
      clearTimeout(timeoutId);
    }
  }

  function handleCancel() {
    abortRef.current?.abort();
  }

  const explainedCount = explainedFoaIds.size;

  return (
    <div className="flex flex-col gap-6">
      <form onSubmit={handleSubmit} className="flex flex-col gap-3 rounded-md border border-border bg-card p-4">
        <label htmlFor="profile-input" className="font-heading text-sm font-semibold text-foreground">
          Researcher Profile
        </label>
        <textarea
          id="profile-input"
          value={profileText}
          onChange={(e) => setProfileText(e.target.value)}
          maxLength={MAX_LENGTH}
          rows={5}
          disabled={loading}
          placeholder="e.g. I study machine learning methods for analyzing rural community health outcomes, with a focus on underserved populations."
          className="w-full resize-y rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground outline-none focus:ring-2 focus:ring-ring disabled:opacity-60"
        />
        <div className="flex items-center justify-between">
          <p className="text-xs text-muted-foreground">
            {tooShort
              ? `At least ${MIN_LENGTH} characters (${trimmedLength} so far).`
              : `${trimmedLength}/${MAX_LENGTH} characters.`}
          </p>
          {/* Distinct `key`s force React to unmount/remount rather than patch
              the same <button> node's type attribute in place. Without them,
              clicking Cancel (which resolves the pending fetch synchronously
              enough to flip status before the browser's own click default-action
              finishes) let the browser see a button that had become
              type="submit" by the time it acted -- silently re-submitting the
              form and starting a second request right after the cancel.
              Confirmed via traced logs: handleSubmit fired twice, the second
              time with status "error", from a genuine second dispatched event. */}
          {loading ? (
            <Button key="cancel" type="button" variant="outline" size="sm" onClick={handleCancel}>
              <X className="size-4" />
              Cancel
            </Button>
          ) : (
            <Button key="submit" type="submit" size="sm" disabled={trimmedLength < MIN_LENGTH}>
              <WandSparkles className="size-4" />
              Find Matches
            </Button>
          )}
        </div>
      </form>

      {phase === "ranking" && (
        <div className="flex items-center gap-3 rounded-md border border-border bg-card p-4 text-sm text-muted-foreground">
          <Loader2 className="size-4 shrink-0 animate-spin text-primary" />
          Ranking opportunities against your profile...
        </div>
      )}

      {phase === "explaining" && (
        <div className="flex items-center gap-3 rounded-md border border-border bg-card p-4 text-sm text-muted-foreground">
          <Loader2 className="size-4 shrink-0 animate-spin text-primary" />
          Generating AI explanations -- {explainedCount}/{explainWindowSize} ready.
        </div>
      )}

      {phase === "error" && (
        <div className="rounded-md border border-status-closed/30 bg-status-closed/5 p-4 text-sm text-status-closed">
          {errorMessage}
        </div>
      )}

      {(phase === "explaining" || phase === "done") && (
        <div className="flex flex-col gap-4">
          {phase === "done" && !llmAvailable && explainWindowSize > 0 && (
            <div className="flex items-center gap-2 rounded-md border border-status-forecasted/30 bg-status-forecasted/5 p-3 text-sm text-foreground">
              <Info className="size-4 shrink-0 text-status-forecasted" />
              AI-generated explanations are unavailable right now (local LLM unreachable) -- showing
              ranked matches only.
            </div>
          )}
          {results.length === 0 ? (
            <p className="text-sm text-muted-foreground">No matching opportunities found for this profile.</p>
          ) : (
            <>
              <p className="text-sm text-muted-foreground">{results.length} matches, ranked by relevance.</p>
              {results.map((r, index) => (
                <MatchResultCard
                  key={r.foa_id}
                  result={r}
                  isExplaining={
                    phase === "explaining" &&
                    index < explainWindowSize &&
                    !explainedFoaIds.has(r.foa_id)
                  }
                />
              ))}
            </>
          )}
        </div>
      )}
    </div>
  );
}

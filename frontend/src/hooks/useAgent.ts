/**
 * useAgent — React Query hook for the buddy persona (#442).
 *
 * Mirrors the style of useMemoryApi.ts: a useQuery for the read path,
 * a useMutation that invalidates the read query on success.
 *
 * Auth gate: the query is disabled when the user is not authenticated
 * so we never storm /api/v1/me/agent with 401s. Without this gate, a
 * logged-out visit to /my-agent fired hundreds of requests per second
 * (each with a freshly-generated child_id) — see commit message for
 * the runaway-loop fix.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AxiosError } from "axios";
import { agentService } from "@/api/services/agentService";
import useAuthStore from "@/store/useAuthStore";
import type { Agent, UpsertAgentPayload } from "@/types/agent";

const AGENT_QUERY_KEY = (childId: string | undefined) =>
  ["agent", childId ?? null] as const;

export function useAgent(childId: string | undefined | null) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const enabled = Boolean(childId) && isAuthenticated;
  return useQuery<Agent | null>({
    queryKey: AGENT_QUERY_KEY(childId ?? undefined),
    queryFn: () => agentService.getAgent(childId as string),
    enabled,
    staleTime: 60_000,
    // Don't retry on 401 — the request will keep failing until the user
    // signs in. Retrying just multiplies the noise (and on a network
    // error, our existing service already throws cleanly).
    retry: (failureCount, error) => {
      if (error instanceof AxiosError && error.response?.status === 401) {
        return false;
      }
      return failureCount < 2;
    },
  });
}

export function useUpsertAgent() {
  const qc = useQueryClient();
  return useMutation<Agent, unknown, UpsertAgentPayload>({
    mutationFn: (payload) => agentService.putAgent(payload),
    onSuccess: (data) => {
      qc.setQueryData(AGENT_QUERY_KEY(data.child_id), data);
      qc.invalidateQueries({ queryKey: AGENT_QUERY_KEY(data.child_id) });
    },
  });
}

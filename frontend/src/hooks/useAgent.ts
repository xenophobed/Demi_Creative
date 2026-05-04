/**
 * useAgent — React Query hook for the buddy persona (#442).
 *
 * Mirrors the style of useMemoryApi.ts: a useQuery for the read path,
 * a useMutation that invalidates the read query on success.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { agentService } from "@/api/services/agentService";
import type { Agent, UpsertAgentPayload } from "@/types/agent";

const AGENT_QUERY_KEY = (childId: string | undefined) =>
  ["agent", childId ?? null] as const;

export function useAgent(childId: string | undefined | null) {
  const enabled = Boolean(childId);
  return useQuery<Agent | null>({
    queryKey: AGENT_QUERY_KEY(childId ?? undefined),
    queryFn: () => agentService.getAgent(childId as string),
    enabled,
    staleTime: 60_000,
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

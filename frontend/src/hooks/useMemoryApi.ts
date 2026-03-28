/**
 * useMemoryApi - React Query hook for character gallery and preference data
 *
 * When childId is null, automatically resolves the user's primary child_id
 * from story history via GET /memory/child-id.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { memoryService } from '@/api/services/memoryService'

export function useMemoryApi(childId: string | null) {
  const queryClient = useQueryClient()

  // Auto-resolve child_id from story history when not provided
  const { data: resolvedChildData } = useQuery({
    queryKey: ['memory-child-id'],
    queryFn: () => memoryService.getChildId(),
    enabled: !childId,
    staleTime: 5 * 60 * 1000, // Cache for 5 minutes
  })

  const effectiveChildId = childId || resolvedChildData?.child_id || null

  const {
    data: charactersData,
    isLoading: charactersLoading,
    error: charactersError,
  } = useQuery({
    queryKey: ['memory-characters', effectiveChildId],
    queryFn: () => memoryService.getCharacters(effectiveChildId!),
    enabled: !!effectiveChildId,
  })

  const {
    data: preferencesData,
    isLoading: preferencesLoading,
    error: preferencesError,
  } = useQuery({
    queryKey: ['memory-preferences', effectiveChildId],
    queryFn: () => memoryService.getPreferences(effectiveChildId!),
    enabled: !!effectiveChildId,
  })

  const deletePreferencesMutation = useMutation({
    mutationFn: () => memoryService.deletePreferences(effectiveChildId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['memory-characters', effectiveChildId] })
      queryClient.invalidateQueries({ queryKey: ['memory-preferences', effectiveChildId] })
    },
  })

  return {
    childId: effectiveChildId,
    characters: charactersData?.characters ?? [],
    preferences: preferencesData?.profile ?? null,
    isLoading: charactersLoading || preferencesLoading,
    error: charactersError || preferencesError,
    deletePreferences: deletePreferencesMutation.mutateAsync,
    isDeleting: deletePreferencesMutation.isPending,
    deleteError: deletePreferencesMutation.error,
  }
}

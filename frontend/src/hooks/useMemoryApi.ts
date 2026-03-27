/**
 * useMemoryApi - React Query hook for character gallery and preference data
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { memoryService } from '@/api/services/memoryService'

export function useMemoryApi(childId: string | null) {
  const queryClient = useQueryClient()

  const {
    data: charactersData,
    isLoading: charactersLoading,
    error: charactersError,
  } = useQuery({
    queryKey: ['memory-characters', childId],
    queryFn: () => memoryService.getCharacters(childId!),
    enabled: !!childId,
  })

  const {
    data: preferencesData,
    isLoading: preferencesLoading,
    error: preferencesError,
  } = useQuery({
    queryKey: ['memory-preferences', childId],
    queryFn: () => memoryService.getPreferences(childId!),
    enabled: !!childId,
  })

  const deletePreferencesMutation = useMutation({
    mutationFn: () => memoryService.deletePreferences(childId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['memory-characters', childId] })
      queryClient.invalidateQueries({ queryKey: ['memory-preferences', childId] })
    },
  })

  return {
    characters: charactersData?.characters ?? [],
    preferences: preferencesData?.profile ?? null,
    isLoading: charactersLoading || preferencesLoading,
    error: charactersError || preferencesError,
    deletePreferences: deletePreferencesMutation.mutateAsync,
    isDeleting: deletePreferencesMutation.isPending,
    deleteError: deletePreferencesMutation.error,
  }
}

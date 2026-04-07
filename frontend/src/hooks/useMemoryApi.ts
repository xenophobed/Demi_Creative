/**
 * useMemoryApi - React Query hook for character gallery and preference data
 *
 * When childId is null, automatically resolves the user's primary child_id
 * from story history via GET /memory/child-id.
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { memoryService } from "@/api/services/memoryService";
import type {
  MemoryCharacter,
  MemoryPreferenceCategory,
  PreferenceProfile,
} from "@/types/api";
import useAuthStore from "@/store/useAuthStore";

function normalizeCharacterName(name: string): string {
  if (!name) return "";
  return name
    .normalize("NFKC")
    .replace(/[\u200B-\u200D\uFEFF]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

function normalizedCharacterKey(name: string): string {
  const cleaned = normalizeCharacterName(name);
  const compact = cleaned
    .replace(/\s+/g, "")
    .replace(/[\p{P}\p{S}]/gu, "")
    .toLocaleLowerCase();
  return compact || cleaned.toLocaleLowerCase();
}

function mergeCharacters(items: MemoryCharacter[]): MemoryCharacter[] {
  const merged = new Map<string, MemoryCharacter>();

  for (const item of items) {
    const normalizedName = normalizeCharacterName(item.name || "");
    const key = normalizedCharacterKey(normalizedName);
    if (!key) continue;

    const existing = merged.get(key);
    if (!existing) {
      merged.set(key, {
        ...item,
        name: normalizedName,
      });
      continue;
    }

    const mergedTraits = [
      ...(existing.traits ?? []),
      ...(item.traits ?? []),
    ].filter((t, idx, arr) => !!t && arr.indexOf(t) === idx);

    const existingVisualScore =
      existing.visual_features && typeof existing.visual_features === "object"
        ? Object.keys(existing.visual_features).length
        : 0;
    const incomingVisualScore =
      item.visual_features && typeof item.visual_features === "object"
        ? Object.keys(item.visual_features).length
        : 0;

    const firstSeen =
      [existing.first_seen_at, item.first_seen_at].filter(Boolean).sort()[0] ??
      existing.first_seen_at;
    const lastSeen =
      [existing.last_seen_at, item.last_seen_at]
        .filter(Boolean)
        .sort()
        .slice(-1)[0] ?? existing.last_seen_at;

    merged.set(key, {
      ...existing,
      name:
        existing.name.length >= normalizedName.length
          ? existing.name
          : normalizedName,
      appearance_count:
        Number(existing.appearance_count || 0) +
        Number(item.appearance_count || 0),
      main_story_count:
        Number(existing.main_story_count || 0) +
        Number(item.main_story_count || 0),
      character_role:
        Number(existing.main_story_count || 0) +
          Number(item.main_story_count || 0) >
        0
          ? "main"
          : "other",
      description:
        (item.description?.length || 0) > (existing.description?.length || 0)
          ? item.description
          : existing.description,
      visual_features:
        incomingVisualScore > existingVisualScore
          ? item.visual_features
          : existing.visual_features,
      traits: mergedTraits.length > 0 ? mergedTraits : null,
      first_seen_at: firstSeen,
      last_seen_at: lastSeen,
    });
  }

  return Array.from(merged.values())
    .map((c) => {
      const role: MemoryCharacter["character_role"] =
        Number(c.main_story_count || 0) > 0 ? "main" : "other";
      return {
        ...c,
        character_role: role,
      };
    })
    .sort(
      (a, b) =>
        Number(b.appearance_count || 0) - Number(a.appearance_count || 0),
    );
}

function splitCharacterGroups(
  allCharacters: MemoryCharacter[],
  hintedMain: MemoryCharacter[],
  hintedOther: MemoryCharacter[],
): { main: MemoryCharacter[]; other: MemoryCharacter[] } {
  if (hintedMain.length > 0 || hintedOther.length > 0) {
    return { main: hintedMain, other: hintedOther };
  }

  const main = allCharacters.filter(
    (c) => Number(c.main_story_count || 0) > 0 || c.character_role === "main",
  );
  const other = allCharacters.filter(
    (c) =>
      !(Number(c.main_story_count || 0) > 0 || c.character_role === "main"),
  );
  return { main, other };
}

function profileScore(profile: PreferenceProfile | null): number {
  if (!profile) return 0;
  return (
    Object.keys(profile.themes || {}).length +
    Object.keys(profile.interests || {}).length +
    Object.keys(profile.concepts || {}).length +
    (profile.recent_choices?.length || 0)
  );
}

function memoryDataScore(
  characters: MemoryCharacter[],
  preferences: PreferenceProfile | null,
): number {
  // Characters are visually critical on Profile, so weight them slightly higher.
  return characters.length * 5 + profileScore(preferences);
}

export function useMemoryApi(childId: string | null) {
  const queryClient = useQueryClient();
  const { user } = useAuthStore();
  const shouldResolveChildId = !!user?.user_id;

  // Resolve user's primary child_id for fallback selection
  const {
    data: resolvedChildData,
    isLoading: resolvingChildLoading,
    error: resolvingChildError,
  } = useQuery({
    queryKey: ["memory-child-id", user?.user_id ?? "anonymous"],
    queryFn: () => memoryService.getChildId(),
    enabled: shouldResolveChildId,
    staleTime: 5 * 60 * 1000, // Cache for 5 minutes
  });

  const resolvedChildId = resolvedChildData?.child_id || null;
  const preferredChildId = childId || resolvedChildId || null;
  const fallbackChildId =
    childId && resolvedChildId && childId !== resolvedChildId
      ? resolvedChildId
      : null;

  const {
    data: preferredCharactersData,
    isLoading: preferredCharactersLoading,
    error: preferredCharactersError,
  } = useQuery({
    queryKey: ["memory-characters", preferredChildId],
    queryFn: () => memoryService.getCharacters(preferredChildId!),
    enabled: !!preferredChildId,
  });

  const {
    data: preferredPreferencesData,
    isLoading: preferredPreferencesLoading,
    error: preferredPreferencesError,
  } = useQuery({
    queryKey: ["memory-preferences", preferredChildId],
    queryFn: () => memoryService.getPreferences(preferredChildId!),
    enabled: !!preferredChildId,
  });

  const {
    data: fallbackCharactersData,
    isLoading: fallbackCharactersLoading,
    error: fallbackCharactersError,
  } = useQuery({
    queryKey: ["memory-characters", fallbackChildId],
    queryFn: () => memoryService.getCharacters(fallbackChildId!),
    enabled: !!fallbackChildId,
  });

  const {
    data: fallbackPreferencesData,
    isLoading: fallbackPreferencesLoading,
    error: fallbackPreferencesError,
  } = useQuery({
    queryKey: ["memory-preferences", fallbackChildId],
    queryFn: () => memoryService.getPreferences(fallbackChildId!),
    enabled: !!fallbackChildId,
  });

  const preferredCharacters = mergeCharacters(
    preferredCharactersData?.characters ?? [],
  );
  const preferredMainHint = mergeCharacters(
    preferredCharactersData?.main_characters ?? [],
  );
  const preferredOtherHint = mergeCharacters(
    preferredCharactersData?.other_characters ?? [],
  );
  const preferredPreferences = preferredPreferencesData?.profile ?? null;
  const fallbackCharacters = mergeCharacters(
    fallbackCharactersData?.characters ?? [],
  );
  const fallbackMainHint = mergeCharacters(
    fallbackCharactersData?.main_characters ?? [],
  );
  const fallbackOtherHint = mergeCharacters(
    fallbackCharactersData?.other_characters ?? [],
  );
  const fallbackPreferences = fallbackPreferencesData?.profile ?? null;

  const preferredScore = memoryDataScore(
    preferredCharacters,
    preferredPreferences,
  );
  const fallbackScore = memoryDataScore(
    fallbackCharacters,
    fallbackPreferences,
  );
  const useFallbackData = !!fallbackChildId && fallbackScore > preferredScore;
  const activeChildId = useFallbackData ? fallbackChildId : preferredChildId;

  const activeCharacters = useFallbackData
    ? fallbackCharacters
    : preferredCharacters;
  const groupedCharacters = useFallbackData
    ? splitCharacterGroups(
        fallbackCharacters,
        fallbackMainHint,
        fallbackOtherHint,
      )
    : splitCharacterGroups(
        preferredCharacters,
        preferredMainHint,
        preferredOtherHint,
      );
  const activePreferences = useFallbackData
    ? fallbackPreferences
    : preferredPreferences;

  const primaryLoading =
    !!preferredChildId &&
    (preferredCharactersLoading || preferredPreferencesLoading);
  const fallbackLoading =
    !!fallbackChildId &&
    (fallbackCharactersLoading || fallbackPreferencesLoading);

  const isLoading =
    (!preferredChildId && shouldResolveChildId && resolvingChildLoading) ||
    primaryLoading ||
    (fallbackLoading && preferredScore === 0);

  const primaryError = preferredCharactersError || preferredPreferencesError;
  const fallbackError = fallbackCharactersError || fallbackPreferencesError;
  const activeError = useFallbackData ? fallbackError : primaryError;

  const invalidateChildMemoryQueries = (targetChildId: string | null) => {
    if (!targetChildId) return;
    queryClient.invalidateQueries({
      queryKey: ["memory-characters", targetChildId],
    });
    queryClient.invalidateQueries({
      queryKey: ["memory-preferences", targetChildId],
    });
  };

  const deletePreferencesMutation = useMutation({
    mutationFn: () => memoryService.deletePreferences(activeChildId!),
    onSuccess: () => {
      invalidateChildMemoryQueries(preferredChildId);
      invalidateChildMemoryQueries(fallbackChildId);
      queryClient.invalidateQueries({
        queryKey: ["memory-child-id", user?.user_id ?? "anonymous"],
      });
    },
  });

  const deleteCharacterMutation = useMutation({
    mutationFn: (name: string) =>
      memoryService.deleteCharacter(activeChildId!, name),
    onSuccess: () => {
      invalidateChildMemoryQueries(activeChildId);
    },
  });

  const deletePreferenceItemMutation = useMutation({
    mutationFn: (params: {
      category: MemoryPreferenceCategory;
      label: string;
    }) =>
      memoryService.deletePreferenceItem(
        activeChildId!,
        params.category,
        params.label,
      ),
    onSuccess: () => {
      invalidateChildMemoryQueries(activeChildId);
    },
  });

  return {
    childId: activeChildId,
    characters: activeCharacters,
    mainCharacters: groupedCharacters.main,
    otherCharacters: groupedCharacters.other,
    preferences: activePreferences,
    isLoading,
    error: activeError || (!activeChildId ? resolvingChildError : null),
    deletePreferences: deletePreferencesMutation.mutateAsync,
    isDeleting: deletePreferencesMutation.isPending,
    deleteError: deletePreferencesMutation.error,
    deleteCharacter: deleteCharacterMutation.mutateAsync,
    isDeletingCharacter: deleteCharacterMutation.isPending,
    deleteCharacterError: deleteCharacterMutation.error,
    deletePreferenceItem: deletePreferenceItemMutation.mutateAsync,
    isDeletingPreferenceItem: deletePreferenceItemMutation.isPending,
    deletePreferenceItemError: deletePreferenceItemMutation.error,
  };
}

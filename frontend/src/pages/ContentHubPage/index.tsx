/**
 * ContentHubPage — group directory at /content-hub.
 *
 * Renders:
 *   - "My Groups" section (joined groups; private groups always show here)
 *   - "Public Groups" section
 *   - "Create a new group" CTA → opens GroupCreateModal
 *
 * Joined-state derivation: a group counts as "joined" if it appears
 * in the listing for the current user — the backend's list endpoint
 * already returns public + caller's joined private groups, so we can
 * simply split by visibility for the My/Public columns. (Full
 * membership detail will arrive when #452 lands GET memberships.)
 *
 * Issue: #451 | Parent epic: #437
 */

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { hubService } from "@/api/services/hubService";
import useAuthStore from "@/store/useAuthStore";
import SignInPrompt from "@/components/common/SignInPrompt";
import type {
  CreateGroupPayload,
  Group,
  ListGroupsResponse,
} from "@/types/hub";
import GroupCard from "./GroupCard";
import GroupCreateModal from "./GroupCreateModal";

const HUB_GROUPS_KEY = ["hub-groups"] as const;

export default function ContentHubPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const onboardedAt = useAuthStore((s) => s.user?.onboarded_at);
  const [createOpen, setCreateOpen] = useState(false);
  const [joinError, setJoinError] = useState<string | null>(null);

  const { data, isLoading } = useQuery<ListGroupsResponse>({
    queryKey: HUB_GROUPS_KEY,
    queryFn: () => hubService.listGroups(),
    enabled: isAuthenticated,
  });

  const createMutation = useMutation({
    mutationFn: (payload: CreateGroupPayload) =>
      hubService.createGroup(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: HUB_GROUPS_KEY });
    },
  });

  const joinMutation = useMutation({
    mutationFn: ({ groupId }: { groupId: string }) =>
      hubService.joinGroup(groupId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: HUB_GROUPS_KEY });
    },
  });

  const handleCreate = async (payload: CreateGroupPayload): Promise<Group> => {
    return createMutation.mutateAsync(payload);
  };

  const handleOpen = (group: Group) => {
    navigate(`/content-hub/${group.slug}`);
  };

  const handleJoin = async (group: Group) => {
    setJoinError(null);
    if (group.visibility === "private") {
      setJoinError(
        "This is a private group — open the invite link a friend sent you to join.",
      );
      return;
    }
    try {
      await joinMutation.mutateAsync({ groupId: group.group_id });
    } catch {
      setJoinError("Couldn't join that group. Try again.");
    }
  };

  const items = data?.items ?? [];
  const myGroups = items.filter((g) => g.visibility === "private");
  const publicGroups = items.filter((g) => g.visibility === "public");
  const canCreate = isAuthenticated && Boolean(onboardedAt);

  if (!isAuthenticated) {
    return (
      <div className="mx-auto flex max-w-4xl flex-col gap-6 px-4 py-8">
        <header>
          <h1 className="text-2xl font-semibold text-gray-900">Content Hub</h1>
          <p className="text-sm text-gray-600">
            Browse stories from other kids and start groups around the themes
            you love.
          </p>
        </header>
        <SignInPrompt
          icon="🌐"
          title="Sign in to join the Hub"
          description="The Hub is where kids share stories with each other. Sign in to browse public groups, post your own creations under your buddy's name, and react to others'."
        />
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6 px-4 py-8">
      <header className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Content Hub</h1>
          <p className="text-sm text-gray-600">
            Browse stories from other kids, or start a group around your
            favourite theme. Stories you share show your buddy's name and
            animal — never your real name.
          </p>
        </div>
        {canCreate ? (
          <button
            type="button"
            className="shrink-0 rounded-md bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-700"
            onClick={() => setCreateOpen(true)}
          >
            + New group
          </button>
        ) : (
          <button
            type="button"
            className="shrink-0 rounded-md border border-violet-300 bg-white px-4 py-2 text-sm font-medium text-violet-700 hover:bg-violet-50"
            onClick={() =>
              navigate(`/my-agent?return=${encodeURIComponent("/content-hub")}`)
            }
            title="Meet your buddy first to create a group"
          >
            Meet buddy → New group
          </button>
        )}
      </header>

      {joinError && (
        <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          {joinError}
        </p>
      )}

      {isLoading && <p className="text-gray-500">Loading…</p>}

      {!isLoading && items.length === 0 && (
        <div className="rounded-2xl border-2 border-dashed border-gray-200 bg-white p-8 text-center">
          <p className="text-base font-medium text-gray-700">
            No groups yet — be the first!
          </p>
          <p className="mt-1 text-sm text-gray-500">
            {canCreate
              ? "Create a group around a theme you love and invite friends."
              : "Meet your buddy first, then come back to start your own group."}
          </p>
          <button
            type="button"
            className="mt-4 rounded-md bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-700"
            onClick={() =>
              canCreate
                ? setCreateOpen(true)
                : navigate(
                    `/my-agent?return=${encodeURIComponent("/content-hub")}`,
                  )
            }
          >
            {canCreate ? "Create the first group" : "Meet your buddy first"}
          </button>
        </div>
      )}

      {myGroups.length > 0 && (
        <section className="flex flex-col gap-2">
          <h2 className="text-base font-semibold text-gray-800">My groups</h2>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {myGroups.map((g) => (
              <GroupCard
                key={g.group_id}
                group={g}
                onOpen={() => handleOpen(g)}
                joined={true}
              />
            ))}
          </div>
        </section>
      )}

      {publicGroups.length > 0 && (
        <section className="flex flex-col gap-2">
          <h2 className="text-base font-semibold text-gray-800">
            Public groups
          </h2>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {publicGroups.map((g) => (
              <GroupCard
                key={g.group_id}
                group={g}
                onOpen={() => handleOpen(g)}
                onJoin={() => handleJoin(g)}
                joined={false}
              />
            ))}
          </div>
        </section>
      )}

      <GroupCreateModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreate={handleCreate}
      />
    </div>
  );
}

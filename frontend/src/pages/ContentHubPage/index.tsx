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
import { KeyRound, Plus, Sparkles, Users } from "lucide-react";
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
import JoinPrivateGroupModal from "./JoinPrivateGroupModal";

const HUB_GROUPS_KEY = ["hub-groups"] as const;

export default function ContentHubPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const onboardedAt = useAuthStore((s) => s.user?.onboarded_at);
  const [createOpen, setCreateOpen] = useState(false);
  const [joinByCodeOpen, setJoinByCodeOpen] = useState(false);
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

  const joinByInviteMutation = useMutation({
    mutationFn: (inviteToken: string) => hubService.joinByInvite(inviteToken),
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

  const handleJoinByInvite = async (inviteToken: string) => {
    const group = await joinByInviteMutation.mutateAsync(inviteToken);
    navigate(`/content-hub/${group.slug}`);
  };

  const items = data?.items ?? [];
  const myGroups = items.filter((g) => g.visibility === "private");
  const publicGroups = items.filter((g) => g.visibility === "public");
  const canCreate = isAuthenticated && Boolean(onboardedAt);

  if (!isAuthenticated) {
    return (
      <div className="k12-page-narrow">
        <header className="k12-hero">
          <h1 className="k12-hero-title">Content Hub</h1>
          <p className="k12-hero-copy">
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
    <div className="k12-page">
      <header className="k12-hero flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="mb-2 inline-flex items-center gap-2 rounded-full bg-white/75 px-3 py-1 text-xs font-bold text-primary-dark">
            <Users size={14} />
            Shared stories, safe names
          </div>
          <h1 className="k12-hero-title">Content Hub</h1>
          <p className="k12-hero-copy">
            Browse stories from other kids, or start a group around your
            favourite theme. Stories you share show your buddy's name and
            animal — never your real name.
          </p>
        </div>
        {canCreate ? (
          <div className="flex shrink-0 flex-col gap-2 sm:flex-row">
            <button
              type="button"
              className="k12-button-secondary"
              onClick={() => setJoinByCodeOpen(true)}
            >
              <KeyRound size={16} /> Join with code
            </button>
            <button
              type="button"
              className="k12-button-primary"
              onClick={() => setCreateOpen(true)}
            >
              <Plus size={16} /> New group
            </button>
          </div>
        ) : (
          <button
            type="button"
            className="k12-button-secondary shrink-0"
            onClick={() =>
              navigate(`/my-agent?return=${encodeURIComponent("/content-hub")}`)
            }
            title="Meet your buddy first to create a group"
          >
            <Sparkles size={16} /> Meet buddy first
          </button>
        )}
      </header>

      {joinError && (
        <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          {joinError}
        </p>
      )}

      {isLoading && <p className="text-gray-500">Loading…</p>}

      {!isLoading && items.length === 0 && (
        <div className="k12-panel border-2 border-dashed border-gray-200 p-8 text-center">
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
            className="k12-button-primary mt-4"
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
          {canCreate && (
            <button
              type="button"
              className="k12-button-secondary mt-3"
              onClick={() => setJoinByCodeOpen(true)}
            >
              <KeyRound size={16} /> Join with code
            </button>
          )}
        </div>
      )}

      {myGroups.length > 0 && (
        <section className="flex flex-col gap-3">
          <h2 className="flex items-center gap-2 text-base font-bold text-gray-800">
            <Sparkles size={18} className="text-primary" /> My groups
          </h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
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
        <section className="flex flex-col gap-3">
          <h2 className="flex items-center gap-2 text-base font-bold text-gray-800">
            <Users size={18} className="text-secondary-dark" />
            Public groups
          </h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
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
      <JoinPrivateGroupModal
        open={joinByCodeOpen}
        onClose={() => setJoinByCodeOpen(false)}
        onJoin={handleJoinByInvite}
      />
    </div>
  );
}

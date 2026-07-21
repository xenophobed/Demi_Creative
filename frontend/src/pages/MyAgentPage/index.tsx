/**
 * MyAgentPage — three exclusive states (#510 follow-up):
 *
 *   1. Guest          → SignInPrompt.
 *   2. Authed, no buddy → OnboardingModal (full-screen). The buddy
 *      doesn't exist yet, so there's nothing else to show — the modal
 *      is the page.
 *   3. Authed, buddy exists → AgentChatPanel as the primary surface +
 *      Configure button in the chat header that opens
 *      PersonaEditorSheet. The persona editor is no longer always
 *      visible; the chat is the page.
 *
 * Splitting cleanly avoids the previous "modal stacked on top of chat
 * which stacked on top of editor" UX. PRD §3.11 — My Agent persona.
 *
 * Parent epic: #436
 */

import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { PanelLeft } from "lucide-react";
import useChildStore from "@/store/useChildStore";
import useAuthStore from "@/store/useAuthStore";
import useAgentChatStore from "@/store/useAgentChatStore";
import { authService } from "@/api/services/authService";
import { useAgent } from "@/hooks/useAgent";
import AgentChatPanel from "./AgentChatPanel";
import AgentSessionListSidebar from "./AgentSessionListSidebar";
import OnboardingModal from "./OnboardingModal";
import PersonaEditorSheet from "./PersonaEditorSheet";
import { shouldAutoOpenOnboarding } from "./onboardingState";
import SignInPrompt from "@/components/common/SignInPrompt";
import { AnimalAvatarIcon } from "@/lib/avatarIcons";

export default function MyAgentPage() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const user = useAuthStore((s) => s.user);
  const currentChild = useChildStore((s) => s.currentChild);
  const childProfiles = useChildStore((s) => s.childProfiles);
  const childProfilesLoading = useChildStore((s) => s.isLoading);
  const loadChildProfiles = useChildStore((s) => s.loadChildProfiles);
  const defaultChildId = useChildStore((s) => s.defaultChildId);
  // Parent accounts must wait for the server-backed child profiles before
  // using an ID. The child store starts with a locally generated fallback
  // ID, which is not owned by the account and causes transient 404s during
  // the first My Agent mount (#763 follow-up).
  const childProfilesResolved =
    user?.role !== "parent" || currentChild != null || childProfiles.length > 0;
  const childId = childProfilesResolved
    ? (currentChild?.child_id ?? defaultChildId)
    : undefined;
  const ageGroup = currentChild?.age_group;

  const onboardedAt = user?.onboarded_at;
  const isPendingChildApproval =
    user?.role === "child" && user?.consent_status === "pending_parent_consent";

  const { data: existing, isLoading } = useAgent(childId);

  const [onboardingOpen, setOnboardingOpen] = useState(false);
  const [editorOpen, setEditorOpen] = useState(false);
  const [approvalNotice, setApprovalNotice] = useState<string | null>(null);
  const [approvalBusy, setApprovalBusy] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const loadSessions = useAgentChatStore((s) => s.loadSessions);
  const resetSessions = useAgentChatStore((s) => s.reset);

  // Load (and reset on child switch) the session list whenever the
  // active child changes. Sessions are scoped to (user, child), so a
  // child switch must never show the previous child's chats (#570).
  useEffect(() => {
    if (!isAuthenticated || !childId) return;
    resetSessions();
    loadSessions(childId).catch((err) => {
      console.error("Failed to load agent chat sessions:", err);
    });
  }, [childId, isAuthenticated, loadSessions, resetSessions]);

  useEffect(() => {
    if (!isAuthenticated || user?.role !== "parent" || childProfiles.length > 0) {
      return;
    }
    loadChildProfiles().catch((err) => {
      console.error("Failed to load child profiles:", err);
    });
  }, [childProfiles.length, isAuthenticated, loadChildProfiles, user?.role]);

  useEffect(() => {
    if (isLoading) return;
    if (
      shouldAutoOpenOnboarding({
        isAuthenticated,
        onboardedAt,
        hasExistingAgent: existing != null,
      })
    ) {
      setOnboardingOpen(true);
    }
  }, [isAuthenticated, onboardedAt, existing, isLoading]);

  const childGreeting = useMemo(() => {
    const childName = currentChild?.name?.trim();
    return childName
      ? `${childName}'s creative buddy`
      : "Meet your creative buddy";
  }, [currentChild?.name]);

  const handleResendParentApproval = async () => {
    setApprovalBusy(true);
    setApprovalNotice(null);
    try {
      const response = await authService.resendParentApproval();
      setApprovalNotice(
        response.approval_url
          ? `Approval link refreshed: ${response.approval_url}`
          : "Approval request refreshed.",
      );
    } catch {
      setApprovalNotice("We could not resend approval right now. Try again later.");
    } finally {
      setApprovalBusy(false);
    }
  };

  // --- State 1: Guest ---------------------------------------------------
  if (!isAuthenticated) {
    return (
      <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-8">
        <header className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold text-gray-900">
            Meet your creative buddy
          </h1>
          <p className="text-sm text-gray-600">
            Your buddy is the name and animal we'll show whenever you share a
            story to Content Hub. Sign in to set yours up.
          </p>
        </header>
        <SignInPrompt
          icon={<AnimalAvatarIcon avatarId="emoji:🦊" size={36} />}
          title="Sign in to meet your buddy"
          description="Once you sign in, we'll walk you through naming your creative buddy and picking its animal — takes under a minute."
        />
      </div>
    );
  }

  if (isPendingChildApproval) {
    return (
      <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-8">
        <header className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold text-gray-900">
            Parent approval needed
          </h1>
          <p className="text-sm text-gray-600">
            A parent or guardian needs to approve this account before the buddy
            and sharing setup can continue.
          </p>
        </header>
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-6">
          <p className="text-sm text-amber-900">
            Approval is pending for {user?.parent_email ?? "your parent or guardian"}.
          </p>
          {approvalNotice && (
            <p className="mt-3 break-all text-xs text-amber-800">
              {approvalNotice}
            </p>
          )}
          <button
            type="button"
            onClick={handleResendParentApproval}
            disabled={approvalBusy}
            className="mt-4 rounded-md bg-amber-600 px-4 py-2 text-sm font-medium text-white hover:bg-amber-700 disabled:opacity-60"
          >
            {approvalBusy ? "Sending..." : "Resend approval request"}
          </button>
        </div>
      </div>
    );
  }

  if (user?.role === "parent" && childProfiles.length === 0 && childProfilesLoading) {
    return (
      <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-8">
        <p className="text-gray-500">Loading child profile...</p>
      </div>
    );
  }

  if (user?.role === "parent" && childProfiles.length === 0) {
    return (
      <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-8">
        <header className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold text-gray-900">
            Set up a child profile
          </h1>
          <p className="text-sm text-gray-600">
            Create a nickname-based profile first so your child's buddy can use
            the right age group and interests.
          </p>
        </header>
        <Link
          to="/profile?tab=children"
          className="inline-flex w-fit rounded-md bg-violet-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-violet-700"
        >
          Add child profile
        </Link>
      </div>
    );
  }

  // --- Loading ---------------------------------------------------------
  if (isLoading) {
    return (
      <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-8">
        <p className="text-gray-500">Loading…</p>
      </div>
    );
  }

  // --- State 2: Authed, no buddy → onboarding only --------------------
  if (!existing || !childId) {
    return (
      <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-8">
        <header className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold text-gray-900">
            {childGreeting}
          </h1>
          <p className="text-sm text-gray-600">
            Let's set up your buddy. We'll walk through name, animal, and a
            quick parent consent step.
          </p>
        </header>
        <div className="rounded-2xl border border-dashed border-violet-200 bg-violet-50/60 p-8 text-center">
          <div className="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-full bg-white text-violet-600 shadow-sm ring-1 ring-violet-100">
            <AnimalAvatarIcon avatarId="emoji:🦊" size={30} />
          </div>
          <p className="text-sm text-gray-700">
            Your buddy isn't set up yet. Take a minute to introduce yourselves.
          </p>
          <button
            type="button"
            onClick={() => setOnboardingOpen(true)}
            className="mt-4 rounded-md bg-violet-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-violet-700 focus:outline-none focus:ring-2 focus:ring-violet-500"
          >
            Start onboarding
          </button>
        </div>
        <OnboardingModal
          open={onboardingOpen}
          childId={childId ?? defaultChildId}
          ageGroup={ageGroup}
          onClose={() => setOnboardingOpen(false)}
        />
      </div>
    );
  }

  // --- State 3: Authed + buddy exists → sessions + chat + configure ---
  return (
    <div className="mx-auto flex h-[calc(100vh-7rem)] max-w-5xl gap-4 px-4 pb-4 pt-6">
      {/* Desktop sidebar */}
      <div className="hidden w-64 shrink-0 md:block">
        <AgentSessionListSidebar childId={childId} ageGroup={ageGroup} />
      </div>

      {/* Mobile drawer */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div
            className="absolute inset-0 bg-black/30"
            onClick={() => setSidebarOpen(false)}
            aria-hidden="true"
          />
          <div className="absolute left-0 top-0 h-full w-72 max-w-[80%] p-3">
            <AgentSessionListSidebar
              childId={childId}
              ageGroup={ageGroup}
              onSelected={() => setSidebarOpen(false)}
            />
          </div>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col gap-2">
        {/* Mobile-only "open chats" toggle */}
        <button
          type="button"
          onClick={() => setSidebarOpen(true)}
          className="inline-flex w-fit items-center gap-1.5 rounded-full border border-gray-200 bg-white px-3 py-1 text-xs font-medium text-gray-600 shadow-sm hover:bg-gray-50 md:hidden"
        >
          <PanelLeft size={14} /> Chats
        </button>
        <AgentChatPanel
          agent={existing}
          childId={childId}
          ageGroup={ageGroup}
          interests={currentChild?.interests ?? []}
          onConfigure={() => setEditorOpen(true)}
        />
      </div>

      <PersonaEditorSheet
        open={editorOpen}
        agent={existing}
        childId={childId}
        ageGroup={ageGroup}
        onClose={() => setEditorOpen(false)}
      />
    </div>
  );
}

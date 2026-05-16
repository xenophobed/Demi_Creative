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
import useChildStore from "@/store/useChildStore";
import useAuthStore from "@/store/useAuthStore";
import { useAgent } from "@/hooks/useAgent";
import AgentChatPanel from "./AgentChatPanel";
import OnboardingModal from "./OnboardingModal";
import PersonaEditorSheet from "./PersonaEditorSheet";
import { shouldAutoOpenOnboarding } from "./onboardingState";
import SignInPrompt from "@/components/common/SignInPrompt";

export default function MyAgentPage() {
  const currentChild = useChildStore((s) => s.currentChild);
  const defaultChildId = useChildStore((s) => s.defaultChildId);
  const childId = currentChild?.child_id ?? defaultChildId;
  const ageGroup = currentChild?.age_group;

  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const onboardedAt = useAuthStore((s) => s.user?.onboarded_at);

  const { data: existing, isLoading } = useAgent(childId);

  const [onboardingOpen, setOnboardingOpen] = useState(false);
  const [editorOpen, setEditorOpen] = useState(false);

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
          icon="🦊"
          title="Sign in to meet your buddy"
          description="Once you sign in, we'll walk you through naming your creative buddy and picking its animal — takes under a minute."
        />
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
          <div className="mx-auto mb-3 text-5xl">🦊</div>
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
          childId={childId}
          ageGroup={ageGroup}
          onClose={() => setOnboardingOpen(false)}
        />
      </div>
    );
  }

  // --- State 3: Authed + buddy exists → chat + configure --------------
  return (
    <div className="mx-auto flex h-[calc(100vh-7rem)] max-w-3xl flex-col gap-4 px-4 pb-4 pt-6">
      <AgentChatPanel
        agent={existing}
        childId={childId}
        ageGroup={ageGroup}
        interests={currentChild?.interests ?? []}
        onConfigure={() => setEditorOpen(true)}
      />
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

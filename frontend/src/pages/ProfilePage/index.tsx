import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { motion } from "framer-motion";
import { useQuery } from "@tanstack/react-query";
import {
  BookOpen,
  Check,
  Flame,
  Gift,
  ImagePlus,
  Newspaper,
  PartyPopper,
  Star,
} from "lucide-react";
import Button from "@/components/common/Button";
import Card from "@/components/common/Card";
import TiltCard from "@/components/depth/TiltCard";
import useAuthStore from "@/store/useAuthStore";
import useChildStore from "@/store/useChildStore";
import useDailyTaskStore from "@/store/useDailyTaskStore";
import { authService } from "@/api/services/authService";
import { libraryService } from "@/api/services/libraryService";
import { achievementService } from "@/api/services/achievementService";
import type { UpdateProfileRequest, ReferralStatus } from "@/types/auth";
import AvatarDisplay from "@/components/common/AvatarDisplay";
import StarPiggyBank from "@/components/daily/StarPiggyBank";
import AchievementBadges from "@/components/profile/AchievementBadges";
import CharacterGallery from "./CharacterGallery";
import PreferenceSummary from "./PreferenceSummary";
import ChildrenTab from "./ChildrenTab";
import { useMemoryApi } from "@/hooks/useMemoryApi";
import type { MemoryPreferenceCategory } from "@/types/api";
import { ANIMAL_EMOJIS } from "@/lib/avatars";
import { AnimalAvatarIcon, normalizeAvatarId } from "@/lib/avatarIcons";

const PROFILE_TABS = [
  { id: "overview", label: "Overview" },
  { id: "children", label: "Children" },
  { id: "memory", label: "Memory" },
  { id: "rewards", label: "Rewards" },
  { id: "account", label: "Account" },
] as const;

type ProfileTabId = (typeof PROFILE_TABS)[number]["id"];

function isProfileTabId(value: string | null): value is ProfileTabId {
  return PROFILE_TABS.some((tab) => tab.id === value);
}

interface ProfileTabsProps {
  activeTab: ProfileTabId;
  onSelect: (tab: ProfileTabId) => void;
}

function ProfileTabs({ activeTab, onSelect }: ProfileTabsProps) {
  return (
    <div className="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
      <div
        className="flex min-w-max gap-2 border-b border-gray-200"
        role="tablist"
        aria-label="Profile sections"
      >
        {PROFILE_TABS.map((tab) => {
          const isActive = activeTab === tab.id;
          return (
            <button
              id={`profile-tab-trigger-${tab.id}`}
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={isActive}
              aria-controls={`profile-tab-panel-${tab.id}`}
              className={`whitespace-nowrap border-b-2 px-4 py-3 text-sm font-bold transition-colors ${
                isActive
                  ? "border-primary text-primary"
                  : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-800"
              }`}
              onClick={() => onSelect(tab.id)}
            >
              {tab.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function StarBoard() {
  const totalStars = useDailyTaskStore((s) => s.totalStars);
  const streak = useDailyTaskStore((s) => s.getStreak());

  return (
    <Card className="overflow-hidden">
      <div className="bg-gradient-to-r from-amber-400 via-yellow-400 to-orange-400 px-5 py-4">
        <div className="flex items-center gap-3">
          <Star className="h-8 w-8 text-white" aria-hidden="true" />
          <div>
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              My Star Collection
              {streak >= 2 && (
                <span className="px-2 py-0.5 text-[10px] font-bold rounded-full bg-white/25 text-white backdrop-blur-sm border border-white/30">
                  <Flame className="h-3 w-3" aria-hidden="true" /> {streak} day streak
                </span>
              )}
            </h2>
            <p className="text-xs text-white/80 mt-0.5">
              Tear the daily newspaper to collect stars!
            </p>
          </div>
        </div>
      </div>

      <div className="p-5 space-y-4">
        {/* Total stars */}
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-gray-500">Total Stars</span>
          <span className="text-2xl font-bold text-amber-500">{totalStars}</span>
        </div>

        {/* Weekly progress with piggy bank */}
        <div>
          <p className="text-xs font-medium text-gray-500 mb-3">This Week</p>
          <div className="flex justify-center">
            <StarPiggyBank />
          </div>
        </div>
      </div>
    </Card>
  );
}

function ProfilePage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { isAuthenticated, user, setUser } = useAuthStore();
  const { currentChild, defaultChildId } = useChildStore();
  const childId = currentChild?.child_id || defaultChildId || null;
  const tabParam = searchParams.get("tab");
  const activeTab: ProfileTabId = isProfileTabId(tabParam)
    ? tabParam
    : "overview";
  const isParent = user?.role === "parent";
  const [isEditing, setIsEditing] = useState(false);
  const [editForm, setEditForm] = useState<UpdateProfileRequest>({
    display_name: user?.display_name || "",
    avatar_url: user?.avatar_url || "",
  });
  const [saving, setSaving] = useState(false);
  const [isMemoryEditMode, setIsMemoryEditMode] = useState(false);
  const [showClearConfirm, setShowClearConfirm] = useState(false);
  const [clearSuccess, setClearSuccess] = useState(false);
  const [clearError, setClearError] = useState<string | null>(null);
  const [deletingCharacterName, setDeletingCharacterName] = useState<
    string | null
  >(null);
  const [deletingPreferenceKey, setDeletingPreferenceKey] = useState<
    string | null
  >(null);
  const [referral, setReferral] = useState<ReferralStatus | null>(null);
  const [referralLoading, setReferralLoading] = useState(false);
  const [linkCopied, setLinkCopied] = useState(false);

  const {
    characters,
    mainCharacters,
    otherCharacters,
    preferences,
    isLoading: memoryLoading,
    error: memoryError,
    deletePreferences,
    deleteCharacter,
    deletePreferenceItem,
    isDeleting,
  } = useMemoryApi(isAuthenticated ? childId : null);

  useEffect(() => {
    if (!isAuthenticated) {
      navigate("/login");
    }
  }, [isAuthenticated, navigate]);

  useEffect(() => {
    const tabParam = searchParams.get("tab");
    if (tabParam && !isProfileTabId(tabParam)) {
      const next = new URLSearchParams(searchParams);
      next.delete("tab");
      setSearchParams(next, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  useEffect(() => {
    if (!isAuthenticated) return;
    setReferralLoading(true);
    authService
      .fetchReferralStatus()
      .then(setReferral)
      .catch((err) => console.error("Failed to load referral status:", err))
      .finally(() => setReferralLoading(false));
  }, [isAuthenticated]);

  // Fetch user stats
  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ["library-counts"],
    queryFn: () => libraryService.getCounts(),
    enabled: isAuthenticated,
  });

  const { data: achievements, isLoading: achievementsLoading } = useQuery({
    queryKey: ["achievements", childId],
    queryFn: () => achievementService.getForChild(childId as string),
    enabled: isAuthenticated && Boolean(childId),
  });

  const handleSaveProfile = async () => {
    setSaving(true);
    try {
      const updated = await authService.updateProfile(editForm);
      setUser(updated);
      setIsEditing(false);
    } catch (err) {
      console.error("Failed to update profile:", err);
    } finally {
      setSaving(false);
    }
  };

  const handleSelectTab = (tab: ProfileTabId) => {
    const next = new URLSearchParams(searchParams);
    if (tab === "overview") {
      next.delete("tab");
    } else {
      next.set("tab", tab);
    }
    setSearchParams(next);
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString("en-US", {
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  };

  const handleClearMemory = async () => {
    setClearError(null);
    try {
      await deletePreferences();
      setShowClearConfirm(false);
      setIsMemoryEditMode(false);
      setClearSuccess(true);
      setTimeout(() => setClearSuccess(false), 3000);
    } catch (err) {
      console.error("Failed to clear memory:", err);
      setClearError("Failed to clear memory. Please try again.");
    }
  };

  const handleDeleteCharacter = async (name: string) => {
    setClearError(null);
    setDeletingCharacterName(name);
    try {
      await deleteCharacter(name);
    } catch (err) {
      console.error("Failed to delete character:", err);
      setClearError("Failed to delete character. Please try again.");
    } finally {
      setDeletingCharacterName(null);
    }
  };

  const handleDeletePreferenceItem = async (
    category: MemoryPreferenceCategory,
    label: string,
  ) => {
    setClearError(null);
    const key = `${category}:${label}`;
    setDeletingPreferenceKey(key);
    try {
      await deletePreferenceItem({ category, label });
    } catch (err) {
      console.error("Failed to delete preference item:", err);
      setClearError("Failed to delete this item. Please try again.");
    } finally {
      setDeletingPreferenceKey(null);
    }
  };

  if (!isAuthenticated) {
    return null;
  }

  return (
    <div className="space-y-6">
      {/* Profile Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <Card className="p-6">
          <div className="flex flex-col items-center text-center sm:flex-row sm:items-center sm:text-left gap-4">
            <AvatarDisplay avatarUrl={user?.avatar_url} size="lg" />
            <div className="flex-1 min-w-0">
              <h1 className="text-2xl font-bold text-gray-800 truncate">
                {user?.display_name || user?.username}
              </h1>
              <p className="text-gray-500 text-sm">@{user?.username}</p>
              <p className="text-gray-400 text-xs">{user?.email}</p>
              {user?.created_at && (
                <p className="text-gray-400 text-xs mt-1">
                  Member since {formatDate(user.created_at)}
                </p>
              )}
            </div>
          </div>
        </Card>
      </motion.div>

      <ProfileTabs activeTab={activeTab} onSelect={handleSelectTab} />

      {activeTab === "overview" && (
        <div
          id="profile-tab-panel-overview"
          role="tabpanel"
          aria-labelledby="profile-tab-trigger-overview"
          className="space-y-6"
        >
      {/* Stats Cards */}
      <motion.div
        className="grid grid-cols-1 gap-4 sm:grid-cols-3"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <TiltCard
          maxTilt={10}
          glare
          className="cursor-pointer"
          onClick={() => navigate("/library?tab=art-stories")}
        >
          <div className="bg-gradient-to-br from-primary/10 to-primary/5 rounded-card p-5 text-center">
            <ImagePlus className="mx-auto mb-2 h-9 w-9 text-primary" aria-hidden="true" />
            <div className="text-3xl font-bold text-gray-800">
              {statsLoading ? "..." : (stats?.art_story_count ?? 0)}
            </div>
            <div className="text-sm text-gray-500 mt-1">Art Stories</div>
          </div>
        </TiltCard>
        <TiltCard
          maxTilt={10}
          glare
          className="cursor-pointer"
          onClick={() => navigate("/library?tab=interactive")}
        >
          <div className="bg-gradient-to-br from-secondary/20 to-secondary/10 rounded-card p-5 text-center">
            <BookOpen className="mx-auto mb-2 h-9 w-9 text-teal-700" aria-hidden="true" />
            <div className="text-3xl font-bold text-gray-800">
              {statsLoading ? "..." : (stats?.interactive_count ?? 0)}
            </div>
            <div className="text-sm text-gray-500 mt-1">Interactive Tales</div>
          </div>
        </TiltCard>
        <TiltCard
          maxTilt={10}
          glare
          className="cursor-pointer"
          onClick={() => navigate("/library?tab=kids-news")}
        >
          <div className="bg-gradient-to-br from-accent/20 to-accent/10 rounded-card p-5 text-center">
            <Newspaper className="mx-auto mb-2 h-9 w-9 text-yellow-700" aria-hidden="true" />
            <div className="text-3xl font-bold text-gray-800">
              {statsLoading ? "..." : (stats?.news_count ?? 0)}
            </div>
            <div className="text-sm text-gray-500 mt-1">Kids News</div>
          </div>
        </TiltCard>
      </motion.div>

      {/* Kids Daily settings shortcut */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15 }}
      >
        <Card className="flex flex-wrap items-center justify-between gap-3 p-4">
          <div>
            <h2 className="text-base font-bold text-gray-800">
              Kids Daily Preferences
            </h2>
            <p className="text-sm text-gray-500">
              Manage topic channels for Kids Daily episodes.
            </p>
          </div>
          <Button
            size="sm"
            variant="outline"
            onClick={() => navigate("/kids-daily")}
          >
            Manage Channels
          </Button>
        </Card>
      </motion.section>
        </div>
      )}

      {activeTab === "rewards" && (
        <div
          id="profile-tab-panel-rewards"
          role="tabpanel"
          aria-labelledby="profile-tab-trigger-rewards"
          className="space-y-6"
        >
      {/* Star Collection Board */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.12 }}
      >
        <StarBoard />
      </motion.section>

      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.13 }}
      >
        <AchievementBadges
          items={achievements?.items ?? []}
          availableDefinitions={achievements?.available_definitions ?? []}
          ageGroup={currentChild?.age_group}
          isLoading={achievementsLoading}
        />
      </motion.section>
        </div>
      )}

      {activeTab === "account" && (
        <div
          id="profile-tab-panel-account"
          role="tabpanel"
          aria-labelledby="profile-tab-trigger-account"
          className="space-y-6"
        >
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <Card className="p-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-lg font-bold text-gray-800">
                Account Details
              </h2>
              <p className="mt-1 text-sm text-gray-500">
                Update your display name and avatar.
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="w-full sm:w-auto"
              onClick={() => {
                setEditForm({
                  display_name: user?.display_name || "",
                  avatar_url: user?.avatar_url || "",
                });
                setIsEditing(!isEditing);
              }}
            >
              {isEditing ? "Cancel" : "Edit Profile"}
            </Button>
          </div>

          {isEditing && (
            <motion.div
              className="mt-4 space-y-3 border-t border-gray-100 pt-4"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
            >
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-600">
                  Display Name
                </label>
                <input
                  type="text"
                  value={editForm.display_name || ""}
                  onChange={(e) =>
                    setEditForm({ ...editForm, display_name: e.target.value })
                  }
                  className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
                  placeholder="Your display name"
                />
              </div>
              <div>
                <label className="mb-2 block text-sm font-medium text-gray-600">
                  Choose Your Avatar
                </label>
                <div className="mb-3 flex items-center gap-3">
                  <AvatarDisplay
                    avatarUrl={editForm.avatar_url || undefined}
                    size="md"
                  />
                  <span className="text-sm text-gray-500">
                    {normalizeAvatarId(editForm.avatar_url)?.startsWith("emoji:")
                      ? "Tap an icon to change"
                      : "Pick your profile icon"}
                  </span>
                </div>
                <div className="flex flex-wrap gap-2">
                  {ANIMAL_EMOJIS.map((emoji, index) => {
                    const emojiValue = `emoji:${emoji}`;
                    const isSelected =
                      normalizeAvatarId(editForm.avatar_url) === emojiValue;
                    return (
                      <motion.button
                        key={emoji}
                        type="button"
                        aria-label={`Choose profile icon ${index + 1}`}
                        className={`flex h-10 w-10 items-center justify-center rounded-lg text-primary transition-all ${
                          isSelected
                            ? "border-2 border-primary bg-primary/10 shadow-md"
                            : "border border-gray-200 hover:border-gray-300 hover:shadow-sm"
                        }`}
                        onClick={() =>
                          setEditForm({ ...editForm, avatar_url: emojiValue })
                        }
                        whileHover={{ scale: 1.15, y: -2 }}
                        whileTap={{ scale: 0.9 }}
                      >
                        <AnimalAvatarIcon avatarId={emojiValue} size={20} />
                      </motion.button>
                    );
                  })}
                </div>
              </div>
              <Button size="sm" onClick={handleSaveProfile} isLoading={saving}>
                Save Changes
              </Button>
            </motion.div>
          )}
        </Card>
      </motion.section>

      {/* Referral Section */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.12 }}
      >
        <Card className="overflow-hidden">
          {/* Header banner */}
          <div className="bg-gradient-to-r from-violet-500 via-purple-500 to-indigo-500 px-5 py-4">
            <div className="flex items-center gap-3">
              <Gift className="h-8 w-8 text-white" aria-hidden="true" />
              <div>
                <h2 className="text-base font-bold text-white flex items-center gap-2">
                  Share the Fun!
                  {referral?.membership_tier === "plus" && (
                    <span className="px-2 py-0.5 text-[10px] font-bold rounded-full bg-white/25 text-white backdrop-blur-sm border border-white/30">
                      Plus Member
                    </span>
                  )}
                </h2>
                <p className="text-xs text-white/75 mt-0.5">
                  Invite friends to create together and unlock more daily uses
                </p>
              </div>
            </div>
          </div>

          {referralLoading ? (
            <div className="p-5 text-center">
              <div className="inline-block w-5 h-5 border-2 border-purple-300 border-t-purple-600 rounded-full animate-spin" />
            </div>
          ) : referral ? (
            <div className="p-5 space-y-5">
              {/* Share link card */}
              <div className="rounded-xl bg-gradient-to-br from-purple-50 to-indigo-50 border border-purple-100 p-4">
                <p className="text-xs font-medium text-purple-600 mb-2">
                  Your invite link
                </p>
                <div className="flex items-center gap-2">
                  <div className="flex-1 px-3 py-2.5 text-sm bg-white rounded-lg border border-purple-200 text-gray-700 truncate font-mono">
                    {referral.share_url}
                  </div>
                  <button
                    onClick={() => {
                      navigator.clipboard.writeText(referral.share_url);
                      setLinkCopied(true);
                      setTimeout(() => setLinkCopied(false), 2000);
                    }}
                    className={`px-4 py-2.5 text-sm font-semibold rounded-lg transition-all whitespace-nowrap ${
                      linkCopied
                        ? "bg-green-500 text-white shadow-green-200 shadow-md"
                        : "bg-gradient-to-r from-violet-500 to-purple-500 text-white hover:from-violet-600 hover:to-purple-600 shadow-purple-200 shadow-md hover:shadow-lg"
                    }`}
                  >
                    {linkCopied ? (
                      <span className="inline-flex items-center gap-1">
                        Copied <Check className="h-3.5 w-3.5" aria-hidden="true" />
                      </span>
                    ) : (
                      "Copy Link"
                    )}
                  </button>
                </div>
              </div>

              {/* Progress section */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <p className="text-xs font-medium text-gray-500">
                    Invite Progress
                  </p>
                  <p className="text-xs font-bold text-purple-600">
                    {referral.qualified_count} / {referral.upgrade_threshold}
                  </p>
                </div>
                {/* Progress bar */}
                <div className="w-full h-3 bg-gray-100 rounded-full overflow-hidden">
                  <motion.div
                    className="h-full rounded-full bg-gradient-to-r from-violet-400 via-purple-500 to-indigo-500"
                    initial={{ width: 0 }}
                    animate={{
                      width: `${Math.min((referral.qualified_count / referral.upgrade_threshold) * 100, 100)}%`,
                    }}
                    transition={{ duration: 0.8, ease: "easeOut" }}
                  />
                </div>
                <p className="text-xs text-gray-400 mt-2">
                  {referral.membership_tier === "plus"
                    ? (
                      <span className="inline-flex items-center gap-1">
                        <PartyPopper className="h-3.5 w-3.5" aria-hidden="true" />
                        You're a Plus member — enjoy 3x daily creations!
                      </span>
                    )
                    : `Invite ${referral.upgrade_threshold - referral.qualified_count} more friends to upgrade to Plus and get 3x daily uses`}
                </p>
              </div>
            </div>
          ) : (
            <div className="p-5 text-center text-sm text-gray-400">
              Unable to load referral info
            </div>
          )}
        </Card>
      </motion.section>

        </div>
      )}

      {activeTab === "children" && (
        <div
          id="profile-tab-panel-children"
          role="tabpanel"
          aria-labelledby="profile-tab-trigger-children"
          className="space-y-6"
        >
          <ChildrenTab isParent={isParent} />
        </div>
      )}

      {activeTab === "memory" && (
        <div
          id="profile-tab-panel-memory"
          role="tabpanel"
          aria-labelledby="profile-tab-trigger-memory"
          className="space-y-6"
        >
      {/* Memory load error */}
      {memoryError && (
        <motion.section
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.18 }}
        >
          <Card className="p-4 border border-amber-200 bg-amber-50">
            <p className="text-sm text-amber-800">
              We couldn't load memory data right now. Please refresh this page
              and try again.
            </p>
          </Card>
        </motion.section>
      )}

      {/* Character Gallery */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
      >
        <CharacterGallery
          characters={characters}
          mainCharacters={mainCharacters}
          otherCharacters={otherCharacters}
          isLoading={memoryLoading}
          isEditMode={isMemoryEditMode}
          onDeleteCharacter={handleDeleteCharacter}
          deletingCharacterName={deletingCharacterName}
        />
      </motion.section>

      {/* Preference Summary */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.25 }}
      >
        <PreferenceSummary
          preferences={preferences}
          isLoading={memoryLoading}
          isEditMode={isMemoryEditMode}
          onDeletePreferenceItem={handleDeletePreferenceItem}
          deletingItemKey={deletingPreferenceKey}
        />
      </motion.section>

      {/* Privacy / Clear Memory */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
      >
        <Card className="p-4">
          <h2 className="text-base font-bold text-gray-800 mb-1">Privacy</h2>
          <p className="text-sm text-gray-500 mb-3">
            Let kids choose what to remove, or clear everything at once.
          </p>

          {clearSuccess && (
            <div className="mb-3 rounded-lg bg-green-50 border border-green-200 px-3 py-2 text-sm text-green-700">
              Memory cleared successfully.
            </div>
          )}

          {!isMemoryEditMode ? (
            <div className="flex flex-wrap items-center gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  setIsMemoryEditMode(true);
                  setShowClearConfirm(false);
                  setClearError(null);
                }}
              >
                Clear Memory
              </Button>
            </div>
          ) : (
            <div className="space-y-3">
              <p className="text-sm text-gray-600">
                Tap the × on characters and tags above to remove only selected
                items.
              </p>
              {clearError && (
                <p className="text-sm text-red-500">{clearError}</p>
              )}
              {!showClearConfirm ? (
                <div className="flex flex-wrap items-center gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    className="border-red-200 text-red-600 hover:bg-red-50"
                    onClick={() => setShowClearConfirm(true)}
                  >
                    Clear All Memory
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => {
                      setIsMemoryEditMode(false);
                      setShowClearConfirm(false);
                      setClearError(null);
                    }}
                  >
                    Done
                  </Button>
                </div>
              ) : (
                <div className="flex flex-wrap items-center gap-2">
                  <p className="text-sm text-red-600 font-medium">
                    Are you sure? This cannot be undone.
                  </p>
                  <Button
                    size="sm"
                    variant="primary"
                    className="bg-red-500 hover:bg-red-600"
                    onClick={handleClearMemory}
                    isLoading={isDeleting}
                  >
                    Yes, Clear All
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => setShowClearConfirm(false)}
                  >
                    Cancel
                  </Button>
                </div>
              )}
            </div>
          )}
        </Card>
      </motion.section>
        </div>
      )}
    </div>
  );
}

export default ProfilePage;

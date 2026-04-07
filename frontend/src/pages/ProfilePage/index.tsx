import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { useQuery } from "@tanstack/react-query";
import Button from "@/components/common/Button";
import Card from "@/components/common/Card";
import TiltCard from "@/components/depth/TiltCard";
import useAuthStore from "@/store/useAuthStore";
import useChildStore from "@/store/useChildStore";
import { authService } from "@/api/services/authService";
import type { UpdateProfileRequest, ReferralStatus } from "@/types/auth";
import AvatarDisplay from "@/components/common/AvatarDisplay";
import CharacterGallery from "./CharacterGallery";
import PreferenceSummary from "./PreferenceSummary";
import { useMemoryApi } from "@/hooks/useMemoryApi";
import type { MemoryPreferenceCategory } from "@/types/api";

const ANIMAL_EMOJIS = [
  "🐶",
  "🐱",
  "🐼",
  "🐨",
  "🦊",
  "🐰",
  "🐸",
  "🦁",
  "🐯",
  "🐮",
  "🐷",
  "🐵",
  "🐔",
  "🐧",
  "🦄",
  "🐲",
  "🐢",
  "🦋",
  "🐬",
  "🐙",
];

function ProfilePage() {
  const navigate = useNavigate();
  const { isAuthenticated, user, setUser } = useAuthStore();
  const { currentChild, defaultChildId } = useChildStore();
  const childId = currentChild?.child_id || defaultChildId || null;
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
    queryKey: ["user-stats"],
    queryFn: () => authService.getUserStats(),
    enabled: isAuthenticated,
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

          {/* Inline Edit Form */}
          {isEditing && (
            <motion.div
              className="mt-4 pt-4 border-t border-gray-100 space-y-3"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
            >
              <div>
                <label className="block text-sm font-medium text-gray-600 mb-1">
                  Display Name
                </label>
                <input
                  type="text"
                  value={editForm.display_name || ""}
                  onChange={(e) =>
                    setEditForm({ ...editForm, display_name: e.target.value })
                  }
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
                  placeholder="Your display name"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-600 mb-2">
                  Choose Your Avatar
                </label>
                <div className="flex items-center gap-3 mb-3">
                  <AvatarDisplay
                    avatarUrl={editForm.avatar_url || undefined}
                    size="md"
                  />
                  <span className="text-sm text-gray-500">
                    {editForm.avatar_url?.startsWith("emoji:")
                      ? "Tap an animal to change"
                      : "Pick your favorite animal!"}
                  </span>
                </div>
                <div className="flex flex-wrap gap-2">
                  {ANIMAL_EMOJIS.map((emoji) => {
                    const emojiValue = `emoji:${emoji}`;
                    const isSelected = editForm.avatar_url === emojiValue;
                    return (
                      <motion.button
                        key={emoji}
                        type="button"
                        className={`w-10 h-10 rounded-lg text-xl flex items-center justify-center transition-all ${
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
                        {emoji}
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
      </motion.div>

      {/* Stats Cards */}
      <motion.div
        className="grid grid-cols-3 gap-4"
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
            <div className="text-4xl mb-2">🎨</div>
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
          <div className="bg-gradient-to-br from-accent/20 to-accent/10 rounded-card p-5 text-center">
            <div className="text-4xl mb-2">🎭</div>
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
          <div className="bg-gradient-to-br from-secondary/20 to-secondary/10 rounded-card p-5 text-center">
            <div className="text-4xl mb-2">📰</div>
            <div className="text-3xl font-bold text-gray-800">
              {statsLoading ? "..." : (stats?.news_count ?? 0)}
            </div>
            <div className="text-sm text-gray-500 mt-1">Kids News</div>
          </div>
        </TiltCard>
      </motion.div>

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
              <div className="text-3xl">🎁</div>
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
                    {linkCopied ? "Copied ✓" : "Copy Link"}
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
                    ? "🎉 You're a Plus member — enjoy 3x daily creations!"
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

      {/* Kids Daily settings shortcut */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15 }}
      >
        <Card className="p-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-bold text-gray-800">
              Kids Daily Preferences
            </h2>
            <p className="text-sm text-gray-500">
              Manage topic channels for Kids Daily episodes.
            </p>
          </div>
          <Button size="sm" variant="outline" onClick={() => navigate("/news")}>
            Manage Channels
          </Button>
        </Card>
      </motion.section>

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
  );
}

export default ProfilePage;

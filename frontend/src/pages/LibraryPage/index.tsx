import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BookOpen,
  Palette,
  Map,
  Newspaper,
  Compass,
  Globe,
  ChevronRight,
  Podcast,
  TrendingUp,
} from "lucide-react";
import Button from "@/components/common/Button";
import Card from "@/components/common/Card";
import useStoryStore from "@/store/useStoryStore";
import useAuthStore from "@/store/useAuthStore";
import useChildStore from "@/store/useChildStore";
import { storyService } from "@/api/services/storyService";
import { libraryService } from "@/api/services/libraryService";
import type {
  LibraryItem,
  LibraryItemType,
  LibrarySortOrder,
} from "@/api/services/libraryService";
import { useAgent } from "@/hooks/useAgent";
import AgentBylineChip from "@/components/common/AgentBylineChip";
import type { Agent } from "@/types/agent";
import { useLibraryPreferences } from "@/hooks/useLibraryPreferences";
import MiniPlayer from "@/components/common/MiniPlayer";
import { getAgeLayoutConfig } from "@/config/ageConfig";
import type { NewsToKidsResponse } from "@/types/api";
import { resolveMediaUrl } from "@/utils/mediaUrl";
import GrowthTimeline from "@/components/library/GrowthTimeline";

// Content type tabs
type ContentTab = "all" | "art-stories" | "interactive" | "kids-news";

const TABS: { id: ContentTab; label: string; icon: React.ReactNode }[] = [
  { id: "all", label: "All", icon: <BookOpen size={16} /> },
  { id: "art-stories", label: "Art Stories", icon: <Palette size={16} /> },
  { id: "interactive", label: "Interactive", icon: <Map size={16} /> },
  { id: "kids-news", label: "Kids News", icon: <Newspaper size={16} /> },
];

const SORT_OPTIONS: { value: LibrarySortOrder; label: string }[] = [
  { value: "favorite_first", label: "Favourite First" },
  { value: "newest", label: "Newest First" },
  { value: "oldest", label: "Oldest First" },
  { value: "word_count", label: "Longest First" },
];

function tabToApiType(tab: ContentTab): LibraryItemType | undefined {
  if (tab === "art-stories") return "art-story";
  if (tab === "interactive") return "interactive";
  if (tab === "kids-news") return "kids-news";
  return undefined; // 'all'
}

// ---- helpers ----

function truncatePreview(text: string, maxLen = 120): string {
  if (!text) return "";
  return text.length > maxLen ? `${text.slice(0, maxLen)}...` : text;
}

// ---- Favorite button (#63) ----

function FavoriteButton({
  itemId,
  itemType,
  isFavorited,
  onToggled,
}: {
  itemId: string;
  itemType: LibraryItemType;
  isFavorited: boolean;
  onToggled?: () => void;
}) {
  const [optimistic, setOptimistic] = useState(isFavorited);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    setOptimistic(isFavorited);
  }, [isFavorited]);

  const handleClick = async (e: React.MouseEvent) => {
    e.stopPropagation();
    const next = !optimistic;
    setOptimistic(next);
    setPending(true);
    try {
      if (next) {
        await libraryService.addFavorite(itemId, itemType);
      } else {
        await libraryService.removeFavorite(itemId, itemType);
      }
      onToggled?.();
    } catch {
      setOptimistic(!next); // revert
    } finally {
      setPending(false);
    }
  };

  return (
    <motion.button
      onClick={handleClick}
      disabled={pending}
      className="text-xl flex-shrink-0 focus:outline-none disabled:opacity-50"
      whileTap={{ scale: 0.8 }}
      title={optimistic ? "Remove from favorites" : "Add to favorites"}
    >
      {optimistic ? "★" : "☆"}
    </motion.button>
  );
}

// ---- Search bar (#62) ----

function SearchBar({
  onSearch,
  isLoading,
}: {
  onSearch: (query: string) => void;
  isLoading: boolean;
}) {
  const [query, setQuery] = useState("");

  useEffect(() => {
    const timer = setTimeout(() => {
      if (query.length >= 2) {
        onSearch(query);
      } else if (query.length === 0) {
        onSearch("");
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [query, onSearch]);

  return (
    <div className="relative">
      <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">
        🔍
      </span>
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search your library..."
        className="w-full pl-10 pr-10 py-2.5 rounded-btn bg-white/80 border border-gray-200 focus:border-primary focus:ring-2 focus:ring-primary/20 outline-none text-sm"
      />
      {isLoading && (
        <span className="absolute right-10 top-1/2 -translate-y-1/2 text-gray-400 animate-spin text-sm">
          ⏳
        </span>
      )}
      {query && (
        <button
          onClick={() => setQuery("")}
          className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
        >
          ✕
        </button>
      )}
    </div>
  );
}

// ---- Delete modal + button ----

function ConfirmDeleteModal({
  isOpen,
  itemLabel,
  onConfirm,
  onCancel,
}: {
  isOpen: boolean;
  itemLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <motion.div
        className="fixed inset-0 z-50 flex items-center justify-center p-4"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
      >
        <motion.div
          className="absolute inset-0 bg-black/40"
          onClick={onCancel}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
        />
        <motion.div
          className="relative bg-white rounded-2xl shadow-xl max-w-sm w-full p-6"
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ type: "spring", damping: 25, stiffness: 300 }}
        >
          <div className="text-center mb-5">
            <span className="text-4xl block mb-3">🗑️</span>
            <h3 className="text-lg font-bold text-gray-800 mb-2">
              Delete {itemLabel}?
            </h3>
            <p className="text-gray-500 text-sm">
              This will be permanently removed and cannot be undone.
            </p>
          </div>
          <div className="flex gap-3">
            <button
              className="flex-1 px-4 py-2.5 rounded-xl border-2 border-gray-200 text-gray-700 font-medium hover:bg-gray-50 transition-colors"
              onClick={onCancel}
            >
              Cancel
            </button>
            <button
              className="flex-1 px-4 py-2.5 rounded-xl bg-red-500 text-white font-medium hover:bg-red-600 transition-colors"
              onClick={onConfirm}
            >
              Delete
            </button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

function DeleteButton({ onDelete }: { onDelete: () => void }) {
  return (
    <motion.button
      className="flex-shrink-0 p-1.5 rounded-lg text-gray-400 hover:text-red-500 hover:bg-red-50 transition-colors"
      onClick={(e) => {
        e.stopPropagation();
        onDelete();
      }}
      whileHover={{ scale: 1.1 }}
      whileTap={{ scale: 0.9 }}
      title="Delete"
    >
      <svg
        xmlns="http://www.w3.org/2000/svg"
        className="w-4 h-4"
        viewBox="0 0 20 20"
        fill="currentColor"
      >
        <path
          fillRule="evenodd"
          d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z"
          clipRule="evenodd"
        />
      </svg>
    </motion.button>
  );
}

// ---- card config ----

const TYPE_BADGE: Record<LibraryItemType, { label: string; color: string }> = {
  "art-story": { label: "Art Story", color: "bg-primary/10 text-primary" },
  interactive: {
    label: "Interactive",
    color: "bg-secondary/10 text-secondary",
  },
  "kids-daily": { label: "Kids Daily", color: "bg-orange-100 text-orange-700" },
  news: { label: "News", color: "bg-accent/10 text-accent" },
  "morning-show": {
    label: "Kids Daily",
    color: "bg-orange-100 text-orange-700",
  },
  "kids-news": { label: "Kids News", color: "bg-accent/10 text-accent" },
};

const DEFAULT_BADGE = { label: "Story", color: "bg-gray-100 text-gray-700" };

const PODCAST_CATEGORY_EMOJI: Record<string, string> = {
  space: "\ud83d\ude80",
  animals: "\ud83d\udc3c",
  technology: "\ud83e\udd16",
  science: "\ud83d\udd2c",
  nature: "\ud83c\udf3f",
  culture: "\ud83c\udfad",
  sports: "\u26bd",
  general: "\ud83c\udf1f",
};

const CARD_STYLES: Record<
  LibraryItemType,
  {
    icon: React.ReactNode;
    gradient: string;
    badgeColor: string;
  }
> = {
  "art-story": {
    icon: <Palette size={36} className="text-primary/60" strokeWidth={1.5} />,
    gradient: "from-primary/20 via-secondary/10 to-accent/20",
    badgeColor: "bg-primary/10 text-primary",
  },
  interactive: {
    icon: <Compass size={36} className="text-secondary/60" strokeWidth={1.5} />,
    gradient: "from-secondary/20 via-accent/10 to-primary/20",
    badgeColor: "bg-secondary/10 text-secondary",
  },
  "kids-daily": {
    icon: (
      <Podcast size={36} className="text-orange-500/70" strokeWidth={1.5} />
    ),
    gradient: "from-orange-200/50 via-yellow-100/30 to-rose-200/40",
    badgeColor: "bg-orange-100 text-orange-700",
  },
  news: {
    icon: <Globe size={36} className="text-accent/60" strokeWidth={1.5} />,
    gradient: "from-accent/20 via-primary/10 to-secondary/20",
    badgeColor: "bg-accent/10 text-accent",
  },
  "morning-show": {
    icon: (
      <Podcast size={36} className="text-orange-500/70" strokeWidth={1.5} />
    ),
    gradient: "from-orange-200/50 via-yellow-100/30 to-rose-200/40",
    badgeColor: "bg-orange-100 text-orange-700",
  },
  "kids-news": {
    icon: <Newspaper size={36} className="text-accent/60" strokeWidth={1.5} />,
    gradient: "from-accent/20 via-primary/10 to-secondary/20",
    badgeColor: "bg-accent/10 text-accent",
  },
};

const DEFAULT_CARD_STYLE = {
  icon: <BookOpen size={36} className="text-gray-400" strokeWidth={1.5} />,
  gradient: "from-gray-100 via-gray-50 to-slate-100",
  badgeColor: "bg-gray-100 text-gray-700",
};

const STATUS_COLORS: Record<string, string> = {
  completed: "bg-green-100 text-green-700",
  expired: "bg-gray-100 text-gray-500",
  active: "bg-blue-100 text-blue-700",
};

function statusLabel(status: string): string {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

// ---- unified card ----

function LibraryCard({
  item,
  onClick,
  onDelete,
  showFavorite,
  onFavoriteToggled,
  showWordCount = true,
  agent,
}: {
  item: LibraryItem;
  onClick: () => void;
  onDelete: () => void;
  showFavorite: boolean;
  onFavoriteToggled?: () => void;
  showWordCount?: boolean;
  agent?: Agent | null;
}) {
  const [imgError, setImgError] = useState(false);
  const imgSrc = (item as any).thumbnail_url || item.image_url;
  const style =
    CARD_STYLES[item.type] ?? CARD_STYLES["kids-daily"] ?? DEFAULT_CARD_STYLE;
  const badge =
    TYPE_BADGE[item.type] ?? TYPE_BADGE["kids-daily"] ?? DEFAULT_BADGE;
  const isKidsDailyLike =
    item.type === "morning-show" || item.type === "kids-daily";
  const progress = item.progress ?? 0;
  const durationLabel = item.duration_seconds
    ? `${Math.max(1, Math.round(item.duration_seconds / 60))} min`
    : null;
  const themeTags = (item.themes ?? []).filter(Boolean).slice(0, 3);
  const infoTags =
    item.type === "interactive"
      ? [`${progress}% complete`, ...themeTags].slice(0, 3)
      : isKidsDailyLike
        ? [durationLabel, item.is_new ? "New episode" : null, ...themeTags]
            .filter(Boolean)
            .slice(0, 3)
        : themeTags;
  const previewText = item.preview
    ? truncatePreview(item.preview)
    : item.type === "interactive"
      ? "Continue this adventure to unlock the next branch."
      : isKidsDailyLike
        ? "Tap to listen to this podcast episode!"
        : "";

  // Badge label: use category for news / morning-show
  const badgeLabel =
    (item.type === "news" ||
      item.type === "morning-show" ||
      item.type === "kids-daily") &&
    item.category
      ? item.category.charAt(0).toUpperCase() + item.category.slice(1)
      : badge.label;

  return (
    <Card
      className="cursor-pointer h-full hover:shadow-lg hover:-translate-y-0.5 transition-all duration-200"
      onClick={onClick}
      padding="none"
    >
      <div className="flex flex-col h-full">
        {/* Thumbnail — full-width hero image */}
        <div
          className={`w-full h-36 rounded-t-xl bg-gradient-to-br ${style.gradient} flex items-center justify-center overflow-hidden`}
        >
          {imgSrc && !imgError ? (
            <img
              src={resolveMediaUrl(imgSrc) || ""}
              alt=""
              className="w-full h-full object-cover"
              onError={() => setImgError(true)}
            />
          ) : isKidsDailyLike ? (
            <div className="flex flex-col items-center gap-1">
              <span className="text-5xl">
                {PODCAST_CATEGORY_EMOJI[item.category || ""] ||
                  "\ud83c\udf99\ufe0f"}
              </span>
              <span className="text-xs font-bold text-orange-600/80">
                Kids Daily
              </span>
            </div>
          ) : (
            style.icon
          )}
        </div>

        {/* Content area */}
        <div className="flex-1 min-w-0 flex flex-col p-5">
          {/* Row 1: Badge + Title + Actions */}
          <div className="flex items-start gap-2">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1.5">
                <span
                  className={`text-xs font-semibold px-2 py-0.5 rounded-full ${style.badgeColor}`}
                >
                  {badgeLabel}
                </span>
                {item.type === "interactive" && item.status && (
                  <span
                    className={`text-xs font-medium px-2 py-0.5 rounded-full ${STATUS_COLORS[item.status] || STATUS_COLORS.active}`}
                  >
                    {statusLabel(item.status)}
                  </span>
                )}
                {isKidsDailyLike &&
                  item.is_new &&
                  item.created_at &&
                  Date.now() - new Date(item.created_at).getTime() <
                    7 * 86400000 && (
                    <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700">
                      New
                    </span>
                  )}
              </div>
              <h3 className="text-base font-bold text-gray-800 line-clamp-2">
                {item.title}
              </h3>
              {agent && (
                <AgentBylineChip agent={agent} className="mt-1" />
              )}
            </div>
            <div className="flex items-center gap-1.5 flex-shrink-0">
              {showFavorite && (
                <FavoriteButton
                  itemId={item.id}
                  itemType={item.type}
                  isFavorited={item.is_favorited}
                  onToggled={onFavoriteToggled}
                />
              )}
              <DeleteButton onDelete={onDelete} />
            </div>
          </div>

          {/* Row 2: Preview text (+ progress for interactive) */}
          {previewText && (
            <p className="text-gray-500 text-sm mt-2.5 line-clamp-2 leading-relaxed">
              {previewText}
            </p>
          )}
          {item.type === "interactive" && (
            <div className="mt-3">
              <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
                <span>Progress</span>
                <span>{progress}%</span>
              </div>
              <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                <motion.div
                  className="h-full bg-secondary rounded-full"
                  initial={{ width: 0 }}
                  animate={{ width: `${progress}%` }}
                  transition={{ duration: 0.6, ease: "easeOut" }}
                />
              </div>
            </div>
          )}

          {/* Row 3: Info tags */}
          {infoTags.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-3">
              {infoTags.map((theme) => (
                <span
                  key={theme}
                  className="text-xs px-2.5 py-1 bg-gray-100 text-gray-500 rounded-full"
                >
                  {theme}
                </span>
              ))}
            </div>
          )}

          {/* Spacer pushes footer to bottom */}
          <div className="flex-1 min-h-3" />

          {/* Row 4: Footer — meta left, audio + chevron right */}
          <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-100">
            <div className="flex items-center gap-1.5 text-xs text-gray-400">
              {showWordCount &&
                item.word_count !== undefined &&
                item.word_count > 0 && (
                  <>
                    <span>{item.word_count} words</span>
                    <span aria-hidden="true">·</span>
                  </>
                )}
              {isKidsDailyLike && durationLabel && (
                <>
                  <span>{durationLabel}</span>
                  <span aria-hidden="true">·</span>
                </>
              )}
              <span>
                {new Date(item.created_at).toLocaleDateString("en-US", {
                  month: "short",
                  day: "numeric",
                })}
              </span>
            </div>
            <div className="flex items-center gap-2">
              {item.audio_url && (
                <MiniPlayer itemId={item.id} audioUrl={item.audio_url} />
              )}
              <ChevronRight size={16} className="text-gray-300" />
            </div>
          </div>
        </div>
      </div>
    </Card>
  );
}

// ---- list row (compact view) ----

function ListRow({
  item,
  onClick,
  onDelete,
  showFavorite,
  onFavoriteToggled,
  showWordCount = true,
  agent,
}: {
  item: LibraryItem;
  onClick: () => void;
  onDelete: () => void;
  showFavorite: boolean;
  onFavoriteToggled?: () => void;
  showWordCount?: boolean;
  agent?: Agent | null;
}) {
  const [imgError, setImgError] = useState(false);
  const imgSrc = (item as any).thumbnail_url || item.image_url;
  const badge =
    TYPE_BADGE[item.type] ?? TYPE_BADGE["kids-daily"] ?? DEFAULT_BADGE;
  const style =
    CARD_STYLES[item.type] ?? CARD_STYLES["kids-daily"] ?? DEFAULT_CARD_STYLE;
  const isKidsDailyLike =
    item.type === "morning-show" || item.type === "kids-daily";
  const progress = item.progress ?? 0;
  const durationLabel = item.duration_seconds
    ? `${Math.max(1, Math.round(item.duration_seconds / 60))} min`
    : null;
  const themeTags = (item.themes ?? []).filter(Boolean).slice(0, 2);
  const previewText = item.preview
    ? truncatePreview(item.preview, 90)
    : item.type === "interactive"
      ? "Continue this adventure to see what happens next."
      : isKidsDailyLike
        ? "Tap to listen to this podcast episode!"
        : "";
  const badgeLabel =
    (item.type === "news" ||
      item.type === "morning-show" ||
      item.type === "kids-daily") &&
    item.category
      ? item.category.charAt(0).toUpperCase() + item.category.slice(1)
      : badge.label;

  return (
    <motion.div
      className="group relative cursor-pointer"
      onClick={onClick}
      whileHover={{ y: -2 }}
    >
      <div
        className={`pointer-events-none absolute inset-0 rounded-2xl bg-gradient-to-r ${style.gradient} opacity-25 transition-opacity group-hover:opacity-35`}
      />
      <div className="relative rounded-2xl border border-gray-200/80 bg-white/90 backdrop-blur-sm p-4 shadow-sm transition-all group-hover:shadow-card">
        <div className="flex gap-4">
          {/* Thumbnail */}
          <div
            className={`flex-shrink-0 w-20 h-20 rounded-xl bg-gradient-to-br ${style.gradient} flex items-center justify-center overflow-hidden`}
          >
            {imgSrc && !imgError ? (
              <img
                src={resolveMediaUrl(imgSrc) || ""}
                alt=""
                className="w-full h-full object-cover"
                onError={() => setImgError(true)}
              />
            ) : isKidsDailyLike ? (
              <span className="text-3xl">
                {PODCAST_CATEGORY_EMOJI[item.category || ""] ||
                  "\ud83c\udf99\ufe0f"}
              </span>
            ) : (
              style.icon
            )}
          </div>

          {/* Content */}
          <div className="flex-1 min-w-0 flex flex-col">
            <div className="flex items-start gap-2">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span
                    className={`text-xs font-semibold px-2 py-0.5 rounded-full ${badge.color}`}
                  >
                    {badgeLabel}
                  </span>
                  {item.type === "interactive" && item.status && (
                    <span
                      className={`text-xs font-medium px-2 py-0.5 rounded-full ${STATUS_COLORS[item.status] || STATUS_COLORS.active}`}
                    >
                      {statusLabel(item.status)}
                    </span>
                  )}
                  {isKidsDailyLike &&
                    item.is_new &&
                    item.created_at &&
                    Date.now() - new Date(item.created_at).getTime() <
                      7 * 86400000 && (
                      <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700">
                        New
                      </span>
                    )}
                </div>
                <h4 className="text-base font-semibold text-gray-800 line-clamp-2">
                  {item.title}
                </h4>
                {agent && (
                  <AgentBylineChip agent={agent} className="mt-1" />
                )}
              </div>
              <div className="flex items-center gap-1.5 flex-shrink-0">
                {showFavorite && (
                  <FavoriteButton
                    itemId={item.id}
                    itemType={item.type}
                    isFavorited={item.is_favorited}
                    onToggled={onFavoriteToggled}
                  />
                )}
                <DeleteButton onDelete={onDelete} />
              </div>
            </div>

            {previewText && (
              <p className="text-sm text-gray-500 mt-1.5 line-clamp-1">
                {previewText}
              </p>
            )}
            {item.type === "interactive" && (
              <div className="mt-2">
                <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                  <motion.div
                    className="h-full bg-secondary rounded-full"
                    initial={{ width: 0 }}
                    animate={{ width: `${progress}%` }}
                    transition={{ duration: 0.6, ease: "easeOut" }}
                  />
                </div>
              </div>
            )}
            {themeTags.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-2">
                {themeTags.map((theme) => (
                  <span
                    key={theme}
                    className="text-xs px-2 py-0.5 bg-gray-100 text-gray-500 rounded-full"
                  >
                    {theme}
                  </span>
                ))}
              </div>
            )}

            <div className="flex items-center justify-between mt-2 pt-2 border-t border-gray-100">
              <div className="flex items-center gap-1.5 text-xs text-gray-400">
                {showWordCount &&
                  item.word_count !== undefined &&
                  item.word_count > 0 && (
                    <>
                      <span>{item.word_count} words</span>
                      <span aria-hidden="true">·</span>
                    </>
                  )}
                {isKidsDailyLike && durationLabel && (
                  <>
                    <span>{durationLabel}</span>
                    <span aria-hidden="true">·</span>
                  </>
                )}
                <span>
                  {new Date(item.created_at).toLocaleDateString("en-US", {
                    month: "short",
                    day: "numeric",
                  })}
                </span>
              </div>
              <div className="flex items-center gap-2">
                {item.audio_url && (
                  <MiniPlayer itemId={item.id} audioUrl={item.audio_url} />
                )}
                <ChevronRight size={16} className="text-gray-300" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  );
}

// ---- main page ----

function LibraryPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { storyHistory, clearHistory, setCurrentStory, removeStory } =
    useStoryStore();
  const { isAuthenticated, user } = useAuthStore();
  const { currentChild, defaultChildId } = useChildStore();
  const { viewMode, toggleViewMode } = useLibraryPreferences();
  const childIdForAgent = currentChild?.child_id ?? defaultChildId;
  // Buddy byline (#445) — fetched once for the page; passed into
  // LibraryCard / ListRow so a single agent lookup decorates every card.
  // Disabled when unauthenticated (the hook already guards on a missing
  // child id, but we double-guard here to avoid an extra request).
  const { data: pageAgent } = useAgent(
    isAuthenticated ? childIdForAgent : undefined,
  );
  const ageLayout = getAgeLayoutConfig(currentChild?.age_group);
  const isParent = user?.role === "parent";
  const canShowGrowthTimeline = ageLayout.showGrowthTimeline || isParent;

  const [activeTab, setActiveTab] = useState<ContentTab>("all");
  const [sortOrder, setSortOrder] = useState<LibrarySortOrder>("newest");
  const [searchQuery, setSearchQuery] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<LibraryItem | null>(null);
  const [deletingIds, setDeletingIds] = useState<Set<string>>(new Set());
  const [showGrowthView, setShowGrowthView] = useState(false);
  const [pageSize] = useState(20);
  const [offset, setOffset] = useState(0);

  const isSearching = searchQuery.length >= 2;

  // Reset offset when tab, sort, or search changes
  useEffect(() => {
    setOffset(0);
  }, [activeTab, sortOrder, searchQuery]);

  // ---- data fetching (#61 — unified API for authenticated users) ----

  const apiType = tabToApiType(activeTab);

  // Unified library (authenticated, not searching)
  const { data: libraryData, isLoading: libraryLoading } = useQuery({
    queryKey: ["library", activeTab, sortOrder, offset, pageSize],
    queryFn: () =>
      libraryService.getLibrary({
        type: apiType,
        sort: sortOrder,
        limit: pageSize,
        offset,
      }),
    enabled: isAuthenticated && !isSearching,
  });

  // Search (authenticated, searching)
  const { data: searchData, isLoading: searchLoading } = useQuery({
    queryKey: ["library-search", searchQuery, activeTab, sortOrder, offset],
    queryFn: () =>
      libraryService.searchLibrary({
        q: searchQuery,
        type: apiType,
        sort: sortOrder,
        limit: pageSize,
        offset,
      }),
    enabled: isAuthenticated && isSearching,
  });

  // Fallback data for unauthenticated users — no server calls (#180)
  const childArtStories = undefined;
  const newsHistory = undefined;

  // ---- build items ----

  const activeData = isSearching ? searchData : libraryData;
  const isLoading = isSearching ? searchLoading : libraryLoading;

  // Authenticated: use unified API response
  const serverItems: LibraryItem[] = isAuthenticated
    ? (activeData?.items ?? [])
    : [];
  const serverTotal = isAuthenticated ? (activeData?.total ?? 0) : 0;

  // Unauthenticated: build from local stores (existing fallback behavior)
  const localItems: LibraryItem[] = !isAuthenticated
    ? buildLocalItems(
        storyHistory,
        childArtStories,
        newsHistory,
        activeTab,
        searchQuery,
        sortOrder,
      )
    : [];

  // Filter out items being deleted
  const filterDeleting = (items: LibraryItem[]) =>
    items.filter((i) => !deletingIds.has(i.id));

  const visibleItems = filterDeleting(
    isAuthenticated ? serverItems : localItems,
  );
  const totalItems = isAuthenticated ? serverTotal : localItems.length;
  const hasMore = isAuthenticated && offset + pageSize < serverTotal;

  // ---- handlers ----

  const handleSearch = useCallback((q: string) => {
    setSearchQuery(q);
  }, []);

  const handleItemClick = (item: LibraryItem) => {
    if (item.type === "art-story") {
      const localStory = storyHistory.find((s) => s.story_id === item.id);
      setCurrentStory(localStory ?? null);
      navigate(`/story/${item.id}`);
    } else if (item.type === "interactive") {
      navigate(`/interactive?session=${item.id}`);
    } else if (
      item.type === "morning-show" ||
      item.type === "news" ||
      item.type === "kids-news" ||
      item.type === "kids-daily"
    ) {
      navigate(`/kids-daily/${item.id}`);
    }
  };

  const handleDeleteItem = useCallback(
    async (item: LibraryItem) => {
      setDeletingIds((prev) => new Set(prev).add(item.id));

      if (item.type !== "interactive") {
        removeStory(item.id);
      }

      try {
        if (item.type === "interactive") {
          await storyService.deleteSession(item.id);
        } else {
          await storyService.deleteStory(item.id);
        }
      } catch {
        // Server deletion failed — local removal already happened
      }

      queryClient.invalidateQueries({ queryKey: ["library"] });
      queryClient.invalidateQueries({ queryKey: ["library-search"] });
      queryClient.invalidateQueries({
        queryKey: ["library-child-art-stories"],
      });
      queryClient.invalidateQueries({ queryKey: ["library-news-history"] });
      queryClient.invalidateQueries({ queryKey: ["user-stats"] });
      queryClient.invalidateQueries({ queryKey: ["memory-characters"] });
      queryClient.invalidateQueries({ queryKey: ["memory-preferences"] });
    },
    [queryClient, removeStory],
  );

  const handleClearHistory = () => {
    if (
      window.confirm(
        "Are you sure you want to clear all local story history? This cannot be undone.",
      )
    ) {
      clearHistory();
    }
  };

  const handleLoadMore = () => {
    setOffset((prev) => prev + pageSize);
  };

  const handleFavoriteToggled = () => {
    queryClient.invalidateQueries({ queryKey: ["library"] });
    queryClient.invalidateQueries({ queryKey: ["library-search"] });
  };

  // ---- render ----

  return (
    <div className={`space-y-6 ${ageLayout.fontSize}`}>
      {/* Page header */}
      <motion.div
        className="flex items-center justify-between"
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <h1 className="text-2xl font-bold text-gray-800 flex items-center gap-2">
          <BookOpen size={28} className="text-primary" />
          My Library
        </h1>
        <div className="flex items-center gap-2">
          {/* Growth Timeline toggle — 9-12 age group or parent role (#134, #232) */}
          {canShowGrowthTimeline && isAuthenticated && (
            <motion.button
              onClick={() => setShowGrowthView((v) => !v)}
              className={`p-2 rounded-lg transition-colors ${
                showGrowthView
                  ? "text-primary bg-primary/10"
                  : "text-gray-500 hover:text-primary hover:bg-primary/10"
              }`}
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              title={
                showGrowthView ? "Back to library" : "View growth timeline"
              }
            >
              <TrendingUp size={20} />
            </motion.button>
          )}
          <motion.button
            onClick={toggleViewMode}
            className="p-2 rounded-lg text-gray-500 hover:text-primary hover:bg-primary/10 transition-colors"
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            title={
              viewMode === "grid"
                ? "Switch to list view"
                : "Switch to grid view"
            }
          >
            {viewMode === "grid" ? (
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="w-5 h-5"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <line x1="8" y1="6" x2="21" y2="6" />
                <line x1="8" y1="12" x2="21" y2="12" />
                <line x1="8" y1="18" x2="21" y2="18" />
                <line x1="3" y1="6" x2="3.01" y2="6" />
                <line x1="3" y1="12" x2="3.01" y2="12" />
                <line x1="3" y1="18" x2="3.01" y2="18" />
              </svg>
            ) : (
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="w-5 h-5"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <rect x="3" y="3" width="7" height="7" />
                <rect x="14" y="3" width="7" height="7" />
                <rect x="3" y="14" width="7" height="7" />
                <rect x="14" y="14" width="7" height="7" />
              </svg>
            )}
          </motion.button>
          {storyHistory.length > 0 && !isAuthenticated && (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleClearHistory}
              className="text-gray-500"
            >
              Clear Local History
            </Button>
          )}
        </div>
      </motion.div>

      {/* Search bar (#62) — hidden for 3-5 age group per #114 */}
      {ageLayout.showSearchBar && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
        >
          <SearchBar onSearch={handleSearch} isLoading={searchLoading} />
        </motion.div>
      )}

      {/* Tab bar + sort dropdown (#65) */}
      <motion.div
        className="flex items-center justify-between gap-2"
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <div className="flex gap-2 flex-nowrap overflow-x-auto pb-1 scrollbar-hide">
          {TABS.map((tab) => (
            <motion.button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-1.5 px-4 py-2 rounded-btn font-medium whitespace-nowrap transition-colors ${
                activeTab === tab.id
                  ? "bg-primary text-white shadow-button"
                  : "text-gray-600 bg-white/70 hover:bg-gray-100"
              }`}
              whileHover={{ scale: 1.03 }}
              whileTap={{ scale: 0.97 }}
            >
              {tab.icon}
              <span>{tab.label}</span>
            </motion.button>
          ))}
        </div>

        <select
          value={sortOrder}
          onChange={(e) => setSortOrder(e.target.value as LibrarySortOrder)}
          className="flex-shrink-0 text-sm px-3 py-2 rounded-btn bg-white/80 border border-gray-200 text-gray-600 focus:border-primary focus:ring-2 focus:ring-primary/20 outline-none cursor-pointer"
        >
          {SORT_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </motion.div>

      {/* Growth Timeline view (#134, #232) — replaces content area when active */}
      {showGrowthView && canShowGrowthTimeline && isAuthenticated ? (
        <GrowthTimeline />
      ) : (
        <>
          {/* Loading indicator */}
          {isLoading && visibleItems.length === 0 && (
            <motion.div
              className="text-center py-4 text-gray-400 text-sm"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
            >
              {isSearching ? "Searching..." : "Loading your library..."}
            </motion.div>
          )}

          {/* Content — grid or list */}
          <AnimatePresence mode="popLayout">
            {visibleItems.length > 0 ? (
              <motion.div
                className={
                  viewMode === "grid"
                    ? `grid ${ageLayout.gridClass} gap-5`
                    : "space-y-2"
                }
              >
                {visibleItems.map((item, index) => (
                  <motion.div
                    key={`${item.type}-${item.id}`}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, x: -100 }}
                    transition={{ delay: Math.min(index * 0.04, 0.3) }}
                  >
                    {viewMode === "list" ? (
                      <ListRow
                        item={item}
                        onClick={() => handleItemClick(item)}
                        onDelete={() => setDeleteTarget(item)}
                        showFavorite={isAuthenticated}
                        onFavoriteToggled={handleFavoriteToggled}
                        showWordCount={ageLayout.showWordCount}
                        agent={pageAgent}
                      />
                    ) : (
                      <LibraryCard
                        item={item}
                        onClick={() => handleItemClick(item)}
                        onDelete={() => setDeleteTarget(item)}
                        showFavorite={isAuthenticated}
                        onFavoriteToggled={handleFavoriteToggled}
                        showWordCount={ageLayout.showWordCount}
                        agent={pageAgent}
                      />
                    )}
                  </motion.div>
                ))}

                {/* Load more */}
                {hasMore && (
                  <motion.div
                    className="text-center pt-2"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                  >
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleLoadMore}
                      isLoading={isLoading && offset > 0}
                    >
                      Load More
                    </Button>
                  </motion.div>
                )}
              </motion.div>
            ) : !isLoading ? (
              // Per-tab empty state (#279)
              (() => {
                if (isSearching) {
                  return (
                    <motion.div
                      className="text-center py-16"
                      initial={{ opacity: 0, scale: 0.9 }}
                      animate={{ opacity: 1, scale: 1 }}
                    >
                      <motion.div
                        className="text-8xl mb-6"
                        animate={{ y: [0, -10, 0] }}
                        transition={{ duration: 2, repeat: Infinity }}
                      >
                        🔍
                      </motion.div>
                      <h2 className="text-xl font-bold text-gray-800 mb-2">
                        No results found
                      </h2>
                      <p className="text-gray-500">
                        Try a different search term or clear the search.
                      </p>
                    </motion.div>
                  );
                }

                const TAB_EMPTY_STATES: Record<
                  ContentTab,
                  { icon: string; message: string; cta: string; route: string }
                > = {
                  all: {
                    icon: "🎨",
                    message: "No creations yet — start your first story!",
                    cta: "Upload a Drawing",
                    route: "/upload",
                  },
                  "art-stories": {
                    icon: "🖼️",
                    message: "No art stories yet — upload a drawing!",
                    cta: "Upload a Drawing",
                    route: "/upload",
                  },
                  interactive: {
                    icon: "📖",
                    message: "No interactive tales yet — start one now!",
                    cta: "Start a Story",
                    route: "/interactive",
                  },
                  "kids-news": {
                    icon: "📰",
                    message: "No news stories yet — explore Kids Daily!",
                    cta: "Open Kids Daily",
                    route: "/kids-daily",
                  },
                };
                const emptyState =
                  TAB_EMPTY_STATES[activeTab] ?? TAB_EMPTY_STATES["all"];

                return (
                  <motion.div
                    className="flex flex-col items-center justify-center py-16 text-center"
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                  >
                    <motion.div
                      className="text-6xl mb-4"
                      animate={{ y: [0, -10, 0] }}
                      transition={{ duration: 2, repeat: Infinity }}
                    >
                      {emptyState.icon}
                    </motion.div>
                    <p className="text-lg text-gray-500 mb-6">
                      {emptyState.message}
                    </p>
                    <button
                      onClick={() => navigate(emptyState.route)}
                      className="px-6 py-3 bg-purple-500 text-white rounded-xl font-semibold hover:bg-purple-600 transition-colors"
                    >
                      {emptyState.cta}
                    </button>
                  </motion.div>
                );
              })()
            ) : null}
          </AnimatePresence>

          {/* Footer statistics */}
          {totalItems > 0 && !isSearching && (
            <motion.div
              className="text-center py-4 text-gray-500"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.5 }}
            >
              <p>
                Total:{" "}
                <span className="font-bold text-primary">{totalItems}</span>{" "}
                creations
              </p>
            </motion.div>
          )}
        </>
      )}

      {/* Delete confirmation modal */}
      <ConfirmDeleteModal
        isOpen={deleteTarget !== null}
        itemLabel={
          deleteTarget?.type === "art-story"
            ? "this art story"
            : deleteTarget?.type === "interactive"
              ? "this interactive story"
              : deleteTarget?.type === "morning-show" ||
                  (deleteTarget?.type === "kids-daily" &&
                    !!deleteTarget?.duration_seconds)
                ? "this podcast episode"
                : "this news article"
        }
        onCancel={() => setDeleteTarget(null)}
        onConfirm={() => {
          if (deleteTarget) {
            handleDeleteItem(deleteTarget);
            setDeleteTarget(null);
          }
        }}
      />
    </div>
  );
}

// ---- Local fallback for unauthenticated users ----

function buildLocalItems(
  storyHistory: any[],
  childArtStories: any[] | undefined,
  newsHistory: NewsToKidsResponse[] | undefined,
  activeTab: ContentTab,
  searchQuery: string,
  sortOrder: LibrarySortOrder,
): LibraryItem[] {
  const items: LibraryItem[] = [];
  const queryLower = searchQuery.toLowerCase();

  // Art stories
  if (activeTab === "all" || activeTab === "art-stories") {
    const stories =
      childArtStories && childArtStories.length > 0
        ? childArtStories
        : storyHistory;

    for (const s of stories) {
      const text = s.story?.text || s.story_text || "";
      const item: LibraryItem = {
        id: s.story_id,
        type: "art-story",
        title: `Story #${s.story_id.slice(0, 8)}`,
        preview: text.slice(0, 150),
        image_url:
          s.styled_image_url || s.cover_image_url || (s.image_url ?? null),
        audio_url: s.audio_url ?? null,
        created_at: s.created_at,
        is_favorited: false,
        safety_score: s.safety_score,
        word_count: s.story?.word_count || s.word_count || 0,
        themes: s.educational_value?.themes || s.themes || [],
      };

      if (!searchQuery || text.toLowerCase().includes(queryLower)) {
        items.push(item);
      }
    }
  }

  // News
  if ((activeTab === "all" || activeTab === "kids-news") && newsHistory) {
    for (const n of newsHistory) {
      const item: LibraryItem = {
        id: n.conversion_id,
        type: "news",
        title: n.kid_title,
        preview: n.kid_content,
        image_url: null,
        audio_url: n.audio_url ?? null,
        created_at: n.created_at as unknown as string,
        is_favorited: false,
        category: n.category,
      };

      if (
        !searchQuery ||
        `${n.kid_title} ${n.kid_content}`.toLowerCase().includes(queryLower)
      ) {
        items.push(item);
      }
    }
  }

  // Sort
  if (sortOrder === "oldest") {
    items.sort(
      (a, b) =>
        new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
    );
  } else if (sortOrder === "word_count") {
    items.sort((a, b) => (b.word_count || 0) - (a.word_count || 0));
  } else if (sortOrder === "favorite_first") {
    items.sort(
      (a, b) =>
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
    );
    items.sort((a, b) => Number(b.is_favorited) - Number(a.is_favorited));
  } else {
    items.sort(
      (a, b) =>
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
    );
  }

  return items;
}

export default LibraryPage;

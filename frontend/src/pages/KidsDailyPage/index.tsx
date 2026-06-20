import { useState, useCallback, useRef, useEffect, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Atom,
  Bot,
  Clock3,
  Compass,
  Drama,
  Globe2,
  Leaf,
  Newspaper,
  PawPrint,
  Play,
  Rocket,
  Trophy,
  type LucideIcon,
} from "lucide-react";
import Card from "@/components/common/Card";
import { storyService } from "@/api/services/storyService";
import useAuthStore from "@/store/useAuthStore";
import useChildStore from "@/store/useChildStore";
import useKidsDailyGenerationStore from "@/store/useKidsDailyGenerationStore";
import { kidsDailyGenerationManager } from "@/services/kidsDailyGenerationManager";
import type { NewsCategory } from "@/types/api";
import LoginPrompt from "@/components/common/LoginPrompt";
import QuotaExceededOverlay, {
  isQuotaError,
} from "@/components/common/QuotaExceededOverlay";

const ALL_TOPICS: Array<{
  topic: NewsCategory;
  label: string;
  icon: LucideIcon;
  tagline: string;
}> = [
  {
    topic: "space",
    label: "Space",
    icon: Rocket,
    tagline: "Rockets, planets & stars",
  },
  {
    topic: "animals",
    label: "Animals",
    icon: PawPrint,
    tagline: "Cute, wild & amazing",
  },
  {
    topic: "technology",
    label: "Robots",
    icon: Bot,
    tagline: "Inventions & gadgets",
  },
  {
    topic: "science",
    label: "Science",
    icon: Atom,
    tagline: "Experiments & discoveries",
  },
  {
    topic: "nature",
    label: "Nature",
    icon: Leaf,
    tagline: "Oceans, forests & weather",
  },
  {
    topic: "culture",
    label: "Culture",
    icon: Drama,
    tagline: "Art, music & stories",
  },
  {
    topic: "sports",
    label: "Sports",
    icon: Trophy,
    tagline: "Goals, records & teamwork",
  },
  {
    topic: "general",
    label: "General",
    icon: Newspaper,
    tagline: "A bit of everything",
  },
];

const LOADING_MESSAGES = [
  "Finding cool news...",
  "Reading the headlines...",
  "Writing the script...",
  "Mimi and Duo are rehearsing...",
  "Recording voices...",
  "Almost ready...",
];

const TOPIC_THEME: Record<
  NewsCategory,
  {
    card: string;
    iconBubble: string;
    accentPill: string;
    listenBtn: string;
    listenBtnHover: string;
    followBtn: string;
  }
> = {
  space: {
    card: "from-sky-50 via-blue-50 to-indigo-50 border-sky-200",
    iconBubble: "from-sky-200 to-indigo-200",
    accentPill: "bg-sky-100 text-sky-700",
    listenBtn: "bg-sky-500",
    listenBtnHover: "hover:bg-sky-600 active:bg-sky-700",
    followBtn:
      "border-sky-300 text-sky-700 hover:bg-sky-100 hover:border-sky-500",
  },
  animals: {
    card: "from-emerald-50 via-lime-50 to-green-50 border-emerald-200",
    iconBubble: "from-emerald-200 to-lime-200",
    accentPill: "bg-emerald-100 text-emerald-700",
    listenBtn: "bg-emerald-500",
    listenBtnHover: "hover:bg-emerald-600 active:bg-emerald-700",
    followBtn:
      "border-emerald-300 text-emerald-700 hover:bg-emerald-100 hover:border-emerald-500",
  },
  technology: {
    card: "from-cyan-50 via-blue-50 to-cyan-100 border-cyan-200",
    iconBubble: "from-cyan-200 to-blue-200",
    accentPill: "bg-cyan-100 text-cyan-700",
    listenBtn: "bg-cyan-500",
    listenBtnHover: "hover:bg-cyan-600 active:bg-cyan-700",
    followBtn:
      "border-cyan-300 text-cyan-700 hover:bg-cyan-100 hover:border-cyan-500",
  },
  science: {
    card: "from-warm-100 via-red-50 to-cyan-50 border-primary/20",
    iconBubble: "from-accent/50 to-secondary/35",
    accentPill: "bg-primary/10 text-primary-dark",
    listenBtn: "bg-primary",
    listenBtnHover: "hover:bg-primary-dark active:bg-primary-dark",
    followBtn:
      "border-secondary/35 text-teal-700 hover:bg-secondary/10 hover:border-secondary",
  },
  nature: {
    card: "from-teal-50 via-emerald-50 to-teal-100 border-teal-200",
    iconBubble: "from-teal-200 to-emerald-200",
    accentPill: "bg-teal-100 text-teal-700",
    listenBtn: "bg-teal-500",
    listenBtnHover: "hover:bg-teal-600 active:bg-teal-700",
    followBtn:
      "border-teal-300 text-teal-700 hover:bg-teal-100 hover:border-teal-500",
  },
  culture: {
    card: "from-rose-50 via-pink-50 to-rose-100 border-rose-200",
    iconBubble: "from-rose-200 to-pink-200",
    accentPill: "bg-rose-100 text-rose-700",
    listenBtn: "bg-rose-500",
    listenBtnHover: "hover:bg-rose-600 active:bg-rose-700",
    followBtn:
      "border-rose-300 text-rose-700 hover:bg-rose-100 hover:border-rose-500",
  },
  sports: {
    card: "from-amber-50 via-orange-50 to-yellow-100 border-amber-200",
    iconBubble: "from-amber-200 to-orange-200",
    accentPill: "bg-amber-100 text-amber-700",
    listenBtn: "bg-amber-500",
    listenBtnHover: "hover:bg-amber-600 active:bg-amber-700",
    followBtn:
      "border-amber-300 text-amber-700 hover:bg-amber-100 hover:border-amber-500",
  },
  general: {
    card: "from-slate-50 via-gray-50 to-zinc-100 border-slate-200",
    iconBubble: "from-slate-200 to-zinc-200",
    accentPill: "bg-slate-100 text-slate-700",
    listenBtn: "bg-slate-500",
    listenBtnHover: "hover:bg-slate-600 active:bg-slate-700",
    followBtn:
      "border-slate-300 text-slate-700 hover:bg-slate-100 hover:border-slate-500",
  },
};

/** Bouncing dots animation for loading states */
function BouncingDots() {
  return (
    <span className="inline-flex gap-0.5 ml-1">
      {[0, 1, 2].map((i) => (
        <motion.span
          key={i}
          className="inline-block w-1.5 h-1.5 rounded-full bg-current"
          animate={{ y: [0, -5, 0] }}
          transition={{ duration: 0.5, repeat: Infinity, delay: i * 0.15 }}
        />
      ))}
    </span>
  );
}

/** Full-card overlay shown while generating a podcast */
function GeneratingOverlay({
  Icon,
  topic,
  message,
  onCancel,
}: {
  Icon: LucideIcon;
  topic: string;
  message?: string | null;
  onCancel: () => void;
}) {
  const [msgIndex, setMsgIndex] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setMsgIndex((prev) => (prev + 1) % LOADING_MESSAGES.length);
    }, 3000);
    return () => clearInterval(timer);
  }, []);

  return (
    <motion.div
      className="absolute inset-0 z-10 flex flex-col items-center justify-center rounded-3xl bg-gradient-to-br from-sky-500/90 to-emerald-500/90 backdrop-blur-sm text-white p-4"
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 1.1 }}
    >
      {/* Spinning topic icon */}
      <motion.div
        className="mb-3 flex h-16 w-16 items-center justify-center rounded-2xl border border-white/30 bg-white/20"
        animate={{ rotate: 360 }}
        transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
      >
        <Icon className="h-9 w-9" strokeWidth={2.25} />
      </motion.div>

      {/* Pulsing ring */}
      <motion.div
        className="absolute w-20 h-20 rounded-full border-4 border-white/30"
        animate={{ scale: [1, 1.6, 1], opacity: [0.5, 0, 0.5] }}
        transition={{ duration: 1.5, repeat: Infinity }}
      />

      {/* Topic name */}
      <div className="font-bold text-lg mb-1">{topic}</div>

      {/* Cycling status message */}
      <AnimatePresence mode="wait">
        <motion.div
          key={msgIndex}
          className="text-sm text-white/90 text-center"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.3 }}
        >
          {message || LOADING_MESSAGES[msgIndex]}
          <BouncingDots />
        </motion.div>
      </AnimatePresence>

      {/* Cancel button */}
      <motion.button
        className="mt-3 px-4 py-1.5 rounded-full text-sm font-medium bg-white/20 hover:bg-white/30 active:bg-white/40 text-white border border-white/30 transition-colors"
        onClick={(e) => {
          e.stopPropagation();
          onCancel();
        }}
        whileTap={{ scale: 0.9 }}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1 }}
      >
        Stop
      </motion.button>
    </motion.div>
  );
}

function KidsDailyPage() {
  const { isAuthenticated } = useAuthStore();
  const { currentChild, defaultChildId } = useChildStore();

  const childId = currentChild?.child_id || defaultChildId;
  const ageGroup = currentChild?.age_group || "6-8";

  // Generation progress lives in the store (#727) so it survives a
  // navigation away/back; the manager owns the AbortController + the
  // completion navigation so the episode still opens if the user left.
  const generatingTopic = useKidsDailyGenerationStore((s) => s.generatingTopic);
  const generationMessage = useKidsDailyGenerationStore(
    (s) => s.generationMessage,
  );
  const beginGenerationState = useKidsDailyGenerationStore((s) => s.begin);
  const setGenerationMessage = useKidsDailyGenerationStore((s) => s.setMessage);
  const [subscribedTopics, setSubscribedTopics] = useState<Set<NewsCategory>>(
    () => new Set(),
  );
  const [subscriptionsLoading, setSubscriptionsLoading] = useState(false);
  const [togglingTopic, setTogglingTopic] = useState<NewsCategory | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [rateLimitRetry, setRateLimitRetry] = useState<{
    topic: NewsCategory;
    seconds: number;
  } | null>(null);
  const retryTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const subscribedCount = subscribedTopics.size;
  const subscribedTopicList = useMemo(
    () => new Set(subscribedTopics),
    [subscribedTopics],
  );

  const loadSubscriptions = useCallback(async () => {
    if (!childId) return;
    setSubscriptionsLoading(true);
    try {
      const response = await storyService.getSubscriptions(childId);
      setSubscribedTopics(new Set(response.items.map((item) => item.topic)));
    } catch {
      setError("We couldn't load your news clubs yet. Try refreshing in a moment.");
    } finally {
      setSubscriptionsLoading(false);
    }
  }, [childId]);

  useEffect(() => {
    if (!isAuthenticated) return;
    void loadSubscriptions();
  }, [isAuthenticated, loadSubscriptions]);

  const ensureSubscribed = useCallback(
    async (topic: NewsCategory) => {
      if (!childId || subscribedTopicList.has(topic)) return;
      try {
        await storyService.subscribeTopic({ child_id: childId, topic });
      } catch (err: unknown) {
        const status = (err as { response?: { status?: number } })?.response
          ?.status;
        if (status !== 409) throw err;
      }
      setSubscribedTopics((prev) => new Set(prev).add(topic));
    },
    [childId, subscribedTopicList],
  );

  const handleToggleSubscription = useCallback(
    async (topic: NewsCategory) => {
      if (!childId || generatingTopic || togglingTopic) return;
      setError(null);
      setTogglingTopic(topic);
      try {
        if (subscribedTopicList.has(topic)) {
          await storyService.unsubscribeTopic(childId, topic);
          setSubscribedTopics((prev) => {
            const next = new Set(prev);
            next.delete(topic);
            return next;
          });
        } else {
          await storyService.subscribeTopic({ child_id: childId, topic });
          setSubscribedTopics((prev) => new Set(prev).add(topic));
        }
      } catch (err: unknown) {
        const status = (err as { response?: { status?: number } })?.response
          ?.status;
        if (status === 409) {
          setSubscribedTopics((prev) => new Set(prev).add(topic));
        } else {
          setError("That news club change did not stick. Please try again.");
        }
      } finally {
        setTogglingTopic(null);
      }
    },
    [childId, generatingTopic, subscribedTopicList, togglingTopic],
  );

  const handleListenNow = useCallback(
    async (topic: NewsCategory) => {
      if (!childId || generatingTopic) return;
      setError(null);
      beginGenerationState(topic, "Joining the news club...");

      // Controller + completion navigation are owned by the manager so the
      // run survives this page unmounting mid generation (#727).
      const signal = kidsDailyGenerationManager.beginGeneration();

      try {
        await ensureSubscribed(topic);

        let episodeId: string | null = null;
        await storyService.generateMorningShowOnDemandStream(
          { child_id: childId, category: topic, age_group: ageGroup },
          {
            onStatus: (data) => {
              setGenerationMessage(data.message || "Making your episode...");
            },
            onResult: (data) => {
              episodeId = data?.episode?.episode_id ?? null;
            },
            onError: (data) => {
              throw new Error(data.message || "Episode generation failed.");
            },
          },
          signal,
        );

        if (episodeId) {
          kidsDailyGenerationManager.navigateToEpisode(
            `/kids-daily/${episodeId}`,
          );
        } else {
          setError("The episode finished, but we could not open it yet.");
        }
      } catch (err: unknown) {
        if (signal.aborted) return; // user cancelled — do nothing

        const status = (err as { response?: { status?: number } })?.response
          ?.status ?? (err as { status?: number })?.status;
        const data = (
          err as {
            response?: { data?: { message?: string; retry_after?: number } };
          }
        )?.response?.data;
        const retryAfter =
          data?.retry_after ?? (err as { retry_after?: number })?.retry_after;

        if (status === 429 && retryAfter) {
          // Per-topic rate limit (3/hour)
          setRateLimitRetry({ topic, seconds: retryAfter });
          if (retryTimerRef.current) clearInterval(retryTimerRef.current);
          retryTimerRef.current = setInterval(() => {
            setRateLimitRetry((prev) => {
              if (!prev || prev.seconds <= 1) {
                if (retryTimerRef.current) clearInterval(retryTimerRef.current);
                return null;
              }
              return { ...prev, seconds: prev.seconds - 1 };
            });
          }, 1000);
        } else if (status === 429) {
          // Daily quota exceeded
          setError(
            "You've used all your listens for today - come back tomorrow!",
          );
        } else if (status === 400) {
          setError("Follow this news club first, then tap Listen Now.");
        } else if (status === 502) {
          setError(
            "Our story-makers are taking a quick break — try again in a moment!",
          );
        } else {
          setError("Something went wrong — let's give it another go in a sec!");
        }
      } finally {
        // Clears progress only if this run still owns the controller, so a
        // superseding run (or a cancel) isn't wiped out.
        kidsDailyGenerationManager.finish(signal);
      }
    },
    [
      childId,
      ageGroup,
      generatingTopic,
      ensureSubscribed,
      beginGenerationState,
      setGenerationMessage,
    ],
  );

  const handleCancelGeneration = useCallback(() => {
    kidsDailyGenerationManager.cancel();
  }, []);

  if (!isAuthenticated) {
    return (
      <div className="max-w-lg mx-auto mt-12">
        <LoginPrompt feature="listen to kids news" />
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <motion.div
        className="text-center space-y-3 px-3"
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <motion.span
          className="inline-flex h-16 w-16 items-center justify-center rounded-3xl border border-secondary/25 bg-white shadow-kid-md text-primary"
          animate={{ scale: [1, 1.15, 1], rotate: [0, -5, 5, 0] }}
          transition={{ duration: 3, repeat: Infinity }}
        >
          <Globe2 className="h-9 w-9" strokeWidth={2.1} />
        </motion.span>
        <h1 className="text-2xl md:text-3xl font-bold text-gray-800 mt-2">
          Pick Your News Club
        </h1>
        <p className="text-gray-600 mt-1">
          Choose a topic card, keep your favorites, and listen anytime
        </p>
        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/80 border border-primary/20 shadow-sm">
          <Compass className="h-4 w-4 text-primary" strokeWidth={2.25} />
          <span className="text-sm font-semibold text-gray-700">
            {ALL_TOPICS.length} story channels — pick any to listen
          </span>
        </div>
      </motion.div>

      {/* Quota exceeded overlay */}
      <QuotaExceededOverlay
        show={isQuotaError(error)}
        message={error ?? ""}
        onDismiss={() => setError(null)}
      />

      {/* Error display (non-quota errors) */}
      <AnimatePresence>
        {error && !isQuotaError(error) && (
          <motion.div
            initial={{ opacity: 0, y: -10, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -10, scale: 0.95 }}
          >
            <Card className="border border-red-200 bg-red-50 text-red-700 text-center">
              <p className="text-sm">{error}</p>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>

      {/* All topic cards */}
      <div className="rounded-[30px] border border-sky-100 bg-gradient-to-br from-sky-50 via-white to-emerald-50 p-5 sm:p-6">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {ALL_TOPICS.map((item, index) => {
            const theme = TOPIC_THEME[item.topic];
            const isGenerating = generatingTopic === item.topic;
            const isRateLimited = rateLimitRetry?.topic === item.topic;
            const isSubscribed = subscribedTopicList.has(item.topic);
            const isToggling = togglingTopic === item.topic;
            const TopicIcon = item.icon;

            return (
              <motion.div
                key={item.topic}
                className="relative"
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: Math.min(index * 0.05, 0.3) }}
                whileHover={!isGenerating ? { y: -4 } : {}}
                whileTap={!isGenerating ? { scale: 0.98 } : {}}
              >
                <Card
                  hover={false}
                  padding="none"
                  className={`h-full relative overflow-hidden rounded-3xl border-2 bg-gradient-to-br transition-all shadow-kid-md ${theme.card}`}
                >
                  <div className="h-full min-h-[260px] p-5 flex flex-col gap-3.5">
                    {/* Row 1: Icon */}
                    <div className="h-[66px] flex items-start">
                      <div
                        className={`w-14 h-14 rounded-3xl bg-gradient-to-br ${theme.iconBubble} flex items-center justify-center shadow-sm border border-white/60`}
                      >
                        <motion.div
                          className="text-gray-800/85"
                          animate={{ scale: [1, 1.04, 1] }}
                          transition={{ duration: 4, repeat: Infinity }}
                        >
                          <TopicIcon className="h-8 w-8" strokeWidth={2.1} />
                        </motion.div>
                      </div>
                    </div>

                    {/* Row 2: Title + Tagline (fixed height) */}
                    <div className="h-[88px] text-left">
                      <h3 className="text-lg font-extrabold text-gray-800">
                        {item.label}
                      </h3>
                      <p className="text-sm text-gray-600 leading-snug mt-1">
                        {item.tagline}
                      </p>
                    </div>

                    {/* Row 3: Status hint (fixed height) */}
                    <div className="h-9 flex items-center">
                      {isRateLimited ? (
                        <span className="text-xs font-semibold text-amber-700 bg-amber-100 px-3 py-1 rounded-full">
                          Retry in {rateLimitRetry!.seconds}s
                        </span>
                      ) : isSubscribed ? (
                        <span className="text-xs font-semibold text-emerald-700 bg-emerald-100 px-3 py-1 rounded-full">
                          Following
                        </span>
                      ) : (
                        <span className="text-xs text-gray-600 bg-white/70 px-3 py-1 rounded-full border border-white/80">
                          Tap Follow or Listen
                        </span>
                      )}
                    </div>

                    {/* Row 4: Follow + Listen Now actions */}
                    <div className="mt-auto grid grid-cols-[96px_1fr] gap-2">
                      <motion.button
                        className={`h-12 flex items-center justify-center rounded-2xl text-sm font-bold border transition-colors ${
                          isSubscribed
                            ? "bg-white/80 text-gray-700 border-white"
                            : `${theme.followBtn} bg-white/70`
                        } ${
                          isToggling || subscriptionsLoading
                            ? "cursor-wait opacity-70"
                            : ""
                        }`}
                        disabled={
                          generatingTopic !== null ||
                          isToggling ||
                          subscriptionsLoading
                        }
                        onClick={() => handleToggleSubscription(item.topic)}
                        whileTap={!isToggling ? { scale: 0.95 } : {}}
                      >
                        {isToggling
                          ? "..."
                          : isSubscribed
                            ? "Following"
                            : "Follow"}
                      </motion.button>
                      <motion.button
                        className={`h-12 w-full flex items-center justify-center gap-2 rounded-2xl text-base font-bold border transition-colors ${
                          isGenerating
                            ? "bg-white/70 text-gray-500 border-white cursor-wait"
                            : isRateLimited
                              ? "bg-amber-300 text-amber-900 border-amber-200 cursor-not-allowed"
                              : `${theme.listenBtn} ${theme.listenBtnHover} text-white border-transparent`
                        }`}
                        disabled={generatingTopic !== null || isRateLimited}
                        onClick={() => handleListenNow(item.topic)}
                        whileTap={
                          !isGenerating && !isRateLimited
                            ? { scale: 0.95 }
                            : {}
                        }
                      >
                        {isRateLimited ? (
                          <>
                            <motion.span
                              animate={{ rotate: [0, 180] }}
                              transition={{ duration: 1, repeat: Infinity }}
                            >
                              <Clock3 className="h-4 w-4" strokeWidth={2.25} />
                            </motion.span>
                            Wait {rateLimitRetry!.seconds}s
                          </>
                        ) : (
                          <>
                            <Play
                              className="h-4 w-4 fill-current"
                              strokeWidth={2.25}
                            />
                            Listen Now
                          </>
                        )}
                      </motion.button>
                    </div>
                  </div>

                  {/* Generating overlay */}
                  <AnimatePresence>
                    {isGenerating && (
                      <GeneratingOverlay
                        Icon={TopicIcon}
                        topic={item.label}
                        message={generationMessage}
                        onCancel={handleCancelGeneration}
                      />
                    )}
                  </AnimatePresence>
                </Card>
              </motion.div>
            );
          })}
        </div>
      </div>

      <div className="text-center pb-4 text-xs text-gray-500">
        Following {subscribedCount} news club{subscribedCount === 1 ? "" : "s"}
        . Pick any card and tap Listen — fresh stories every time.
      </div>
    </div>
  );
}

export default KidsDailyPage;

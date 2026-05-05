import { useState, useCallback, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import Card from "@/components/common/Card";
import { storyService } from "@/api/services/storyService";
import useAuthStore from "@/store/useAuthStore";
import useChildStore from "@/store/useChildStore";
import type { NewsCategory } from "@/types/api";
import LoginPrompt from "@/components/common/LoginPrompt";
import QuotaExceededOverlay, {
  isQuotaError,
} from "@/components/common/QuotaExceededOverlay";

const ALL_TOPICS: Array<{
  topic: NewsCategory;
  label: string;
  icon: string;
  tagline: string;
}> = [
  {
    topic: "space",
    label: "Space",
    icon: "\ud83d\ude80",
    tagline: "Rockets, planets & stars",
  },
  {
    topic: "animals",
    label: "Animals",
    icon: "\ud83d\udc3c",
    tagline: "Cute, wild & amazing",
  },
  {
    topic: "technology",
    label: "Robots",
    icon: "\ud83e\udd16",
    tagline: "Inventions & gadgets",
  },
  {
    topic: "science",
    label: "Science",
    icon: "\ud83d\udd2c",
    tagline: "Experiments & discoveries",
  },
  {
    topic: "nature",
    label: "Nature",
    icon: "\ud83c\udf3f",
    tagline: "Oceans, forests & weather",
  },
  {
    topic: "culture",
    label: "Culture",
    icon: "\ud83c\udfad",
    tagline: "Art, music & stories",
  },
  {
    topic: "sports",
    label: "Sports",
    icon: "\u26bd",
    tagline: "Goals, records & teamwork",
  },
  {
    topic: "general",
    label: "General",
    icon: "\ud83d\udcf0",
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
    card: "from-violet-50 via-indigo-50 to-violet-100 border-violet-200",
    iconBubble: "from-violet-200 to-indigo-200",
    accentPill: "bg-violet-100 text-violet-700",
    listenBtn: "bg-violet-500",
    listenBtnHover: "hover:bg-violet-600 active:bg-violet-700",
    followBtn:
      "border-violet-300 text-violet-700 hover:bg-violet-100 hover:border-violet-500",
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
  icon,
  topic,
  onCancel,
}: {
  icon: string;
  topic: string;
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
        className="text-5xl mb-3"
        animate={{ rotate: 360 }}
        transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
      >
        {icon}
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
          {LOADING_MESSAGES[msgIndex]}
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
  const navigate = useNavigate();

  const childId = currentChild?.child_id || defaultChildId;
  const ageGroup = currentChild?.age_group || "6-8";

  const [generatingTopic, setGeneratingTopic] = useState<NewsCategory | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);
  const [rateLimitRetry, setRateLimitRetry] = useState<{
    topic: NewsCategory;
    seconds: number;
  } | null>(null);
  const retryTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const handleListenNow = useCallback(
    async (topic: NewsCategory) => {
      if (!childId || generatingTopic) return;
      setError(null);
      setGeneratingTopic(topic);

      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const result = await storyService.generateMorningShowOnDemand(
          { child_id: childId, category: topic, age_group: ageGroup },
          controller.signal,
        );
        navigate(`/kids-daily/${result.episode.episode_id}`);
      } catch (err: unknown) {
        if (controller.signal.aborted) return; // user cancelled — do nothing

        const status = (err as { response?: { status?: number } })?.response
          ?.status;
        const data = (
          err as {
            response?: { data?: { message?: string; retry_after?: number } };
          }
        )?.response?.data;

        if (status === 429 && data?.retry_after) {
          // Per-topic rate limit (3/hour)
          const retryAfter = data.retry_after;
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
        } else if (status === 502) {
          setError(
            "Our story-makers are taking a quick break — try again in a moment! 🌟",
          );
        } else {
          setError("Something went wrong — let's give it another go in a sec! 🦊");
        }
      } finally {
        abortRef.current = null;
        setGeneratingTopic(null);
      }
    },
    [childId, ageGroup, generatingTopic, navigate],
  );

  const handleCancelGeneration = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setGeneratingTopic(null);
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
          className="text-5xl inline-block"
          animate={{ scale: [1, 1.15, 1], rotate: [0, -5, 5, 0] }}
          transition={{ duration: 3, repeat: Infinity }}
        >
          🌍
        </motion.span>
        <h1 className="text-2xl md:text-3xl font-bold text-gray-800 mt-2">
          Pick Your News Club
        </h1>
        <p className="text-gray-600 mt-1">
          Choose a topic card, keep your favorites, and listen anytime
        </p>
        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/80 border border-primary/20 shadow-sm">
          <span className="text-sm">🌈</span>
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
                          className="text-4xl"
                          animate={{ scale: [1, 1.04, 1] }}
                          transition={{ duration: 4, repeat: Infinity }}
                        >
                          {item.icon}
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
                      ) : (
                        <span className="text-xs text-gray-600 bg-white/70 px-3 py-1 rounded-full border border-white/80">
                          Ready to listen
                        </span>
                      )}
                    </div>

                    {/* Row 4: Listen Now button */}
                    {/* Pink-faded uniform color across all topics, slightly
                        bigger (h-14 + text-lg) per user request. The
                        per-topic theme.listenBtn is no longer used so the
                        button reads as a consistent CTA. */}
                    <div className="mt-auto">
                      <motion.button
                        className={`h-14 w-full flex items-center justify-center gap-2 rounded-2xl text-lg font-bold border transition-all shadow-md hover:shadow-lg ${
                          isGenerating
                            ? "bg-white/70 text-gray-500 border-white cursor-wait"
                            : isRateLimited
                              ? "bg-amber-300 text-amber-900 border-amber-200 cursor-not-allowed"
                              : "bg-gradient-to-r from-rose-300 via-pink-300 to-rose-300 hover:from-rose-400 hover:via-pink-400 hover:to-rose-400 text-white border-transparent"
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
                              ⏳
                            </motion.span>
                            Wait {rateLimitRetry!.seconds}s
                          </>
                        ) : (
                          <>
                            <span>▶</span>
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
                        icon={item.icon}
                        topic={item.label}
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
        Pick any card and tap Listen — fresh stories every time. ✨
      </div>
    </div>
  );
}

export default KidsDailyPage;

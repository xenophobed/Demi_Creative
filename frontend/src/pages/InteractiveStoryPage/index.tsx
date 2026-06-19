import { useState, useEffect, useCallback } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { motion } from "framer-motion";
import Button from "@/components/common/Button";
import Card from "@/components/common/Card";
import AgeAwareContent from "@/components/common/AgeAwareContent";
import EducationalTags from "@/components/story/EducationalTags";
import StorySegmentDisplay from "@/components/interactive/StorySegmentDisplay";
import ChoiceButtons from "@/components/interactive/ChoiceButtons";
import ProgressIndicator from "@/components/interactive/ProgressIndicator";
import ChapterRail, {
  choiceMetaAt,
} from "@/components/interactive/ChapterRail";
import { useChapterScroll } from "@/hooks/useChapterScroll";
import { StreamingVisualizer } from "@/components/streaming/StreamingVisualizer";
import { PerspectiveContainer } from "@/components/depth/PerspectiveContainer";
import { storyService } from "@/api/services/storyService";
import useInteractiveStory from "@/hooks/useInteractiveStory";
import QuotaExceededOverlay, {
  isQuotaError,
} from "@/components/common/QuotaExceededOverlay";
import useStreamVisualization from "@/hooks/useStreamVisualization";
import useAuthStore from "@/store/useAuthStore";
import useChildStore, { DEFAULT_INTERESTS } from "@/store/useChildStore";
import type { AgeGroup, StoryLengthMode } from "@/types/api";
import type { AnimationPhase } from "@/types/streaming";
import ShareToHubModal from "@/components/hub/ShareToHubModal";
import LoginPrompt from "@/components/common/LoginPrompt";
import SuggestedThemes from "@/components/common/SuggestedThemes";
import {
  getInteractiveStoryPageState,
  type InteractiveStoryPageState,
} from "./pageState";
import {
  Baby,
  BookOpen,
  CheckCircle,
  Clock,
  Flag,
  Globe2,
  Home,
  Infinity as InfinityIcon,
  Library,
  Palette,
  Rocket,
  RotateCcw,
  Save,
  Sparkles,
  Sunrise,
  Trophy,
  UserRound,
  UsersRound,
  XCircle,
} from "lucide-react";

const AGE_GROUPS = [
  { value: "3-5" as AgeGroup, label: "3-5 yrs", icon: Baby },
  { value: "6-8" as AgeGroup, label: "6-8 yrs", icon: UserRound },
  { value: "9-12" as AgeGroup, label: "9-12 yrs", icon: UsersRound },
];

const STORY_LENGTHS: {
  value: StoryLengthMode;
  label: string;
  sublabel: string;
  icon: typeof BookOpen;
}[] = [
  { value: "short", label: "Quick Tale", sublabel: "5 choices", icon: BookOpen },
  { value: "medium", label: "Short Story", sublabel: "10 choices", icon: Library },
  { value: "unlimited", label: "Endless Adventure", sublabel: "No limit", icon: InfinityIcon },
];

function InteractiveStoryPageContent() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { currentChild, defaultChildId } = useChildStore();
  const childId = currentChild?.child_id || defaultChildId;

  // Local form state
  const [selectedAge, setSelectedAge] = useState<AgeGroup | null>(
    currentChild?.age_group || null,
  );
  const [selectedLength, setSelectedLength] = useState<StoryLengthMode>("short");
  const [selectedInterests, setSelectedInterests] = useState<string[]>(
    currentChild?.interests?.slice(0, 5) || [],
  );
  const [theme, setTheme] = useState("");
  const [quotaDismissed, setQuotaDismissed] = useState(false);

  // Story hook - use streaming versions for better UX
  const {
    sessionId,
    storyTitle,
    ageGroup: storeAgeGroup,
    storyLengthMode,
    currentSegment,
    segments,
    choiceHistory,
    progress,
    isLoading,
    error,
    isCompleted,
    educationalSummary,
    streaming,
    startStoryStream,
    makeChoiceStream,
    endStory,
    resumeSession,
    reset,
  } = useInteractiveStory();

  // On-demand audio state (for 9-12 age group)
  const [onDemandAudioUrl, setOnDemandAudioUrl] = useState<string | null>(null);
  const [isAudioGenerating, setIsAudioGenerating] = useState(false);

  // Chapter rail — observes which segment is in viewport and exposes scrollTo.
  const {
    containerRef: chapterContainerRef,
    activeIndex: observedChapterIndex,
    scrollProgressMV,
    scrollTo: rawScrollToChapter,
    setActiveIndex: setObservedChapterIndex,
  } = useChapterScroll(segments.length);

  // Optimistic active index — flips immediately on click so the traveler
  // emoji can fly to the target *before* smooth-scroll arrives. The
  // observer keeps things consistent on natural scroll.
  const activeChapterIndex = observedChapterIndex;
  const scrollToChapter = useCallback(
    (index: number) => {
      setObservedChapterIndex(index);
      rawScrollToChapter(index);
    },
    [rawScrollToChapter, setObservedChapterIndex],
  );

  // Use storeAgeGroup during play, selectedAge during setup
  const activeAgeGroup = storeAgeGroup || selectedAge;

  // Stream visualization hook
  const { triggerConfetti } = useStreamVisualization();

  // Map streaming state to animation phase
  const getAnimationPhase = (): AnimationPhase => {
    if (!streaming.isStreaming) return "idle";
    if (streaming.streamStatus === "started") return "connecting";
    if (streaming.thinkingContent) return "thinking";
    if (streaming.streamMessage.includes("tool")) return "tool_executing";
    return "thinking";
  };

  const animationPhase = getAnimationPhase();

  // Save state
  const [saveStatus, setSaveStatus] = useState<
    "idle" | "saving" | "saved" | "error"
  >("idle");

  // Share-to-Content-Hub modal (#453)
  const [shareOpen, setShareOpen] = useState(false);

  // Resume only when URL contains ?session=
  const [isResuming, setIsResuming] = useState(false);
  const [sessionExpiredMsg, setSessionExpiredMsg] = useState<string | null>(
    null,
  );
  const sessionParam = searchParams.get("session");

  // Track whether this mount entered via a deep-link resume URL.
  // When a user lands here from a Content Hub share they clicked "Read"
  // — they did NOT ask for audio. Auto-playing TTS at full volume on
  // cold landing is jarring (and arrived as a real bug report). We
  // suppress auto-play until the user takes their first in-page
  // interaction (e.g. tapping a choice). Captured once at mount so
  // subsequent state changes don't flip it.
  const [enteredViaResume] = useState<boolean>(() => Boolean(sessionParam));
  const [userHasInteracted, setUserHasInteracted] = useState<boolean>(false);
  const audioMaySelfStart =
    activeAgeGroup === "3-5" && (!enteredViaResume || userHasInteracted);

  useEffect(() => {
    // Explicit resume path: /interactive?session=...
    if (sessionParam) {
      let cancelled = false;
      setIsResuming(true);
      setSessionExpiredMsg(null);
      resumeSession(sessionParam)
        .catch((err) => {
          reset();
          if (!cancelled) {
            const isForbidden =
              (err as { response?: { status?: number } })?.response?.status === 403;
            setSessionExpiredMsg(
              isForbidden
                ? "This story belongs to another account. Please switch accounts or start a new story."
                : "This story is no longer available. Please start a new story.",
            );
          }
        })
        .finally(() => {
          if (!cancelled) setIsResuming(false);
        });
      return () => {
        cancelled = true;
      };
    }

    // No session param: always start from clean setup state.
    reset();
    setSessionExpiredMsg(null);
  }, [sessionParam]); // eslint-disable-line react-hooks/exhaustive-deps

  // Track segment changes for reveal animation
  const [isRevealing, setIsRevealing] = useState(false);

  useEffect(() => {
    if (currentSegment && !streaming.isStreaming) {
      setIsRevealing(true);
      const timer = setTimeout(() => setIsRevealing(false), 2000);
      return () => clearTimeout(timer);
    }
  }, [currentSegment, streaming.isStreaming]);

  // Reset on-demand audio when segment changes
  useEffect(() => {
    setOnDemandAudioUrl(null);
    setIsAudioGenerating(false);
  }, [currentSegment?.segment_id]);

  // On-demand audio handler for 9-12 age group
  const handleRequestAudio = useCallback(async () => {
    if (!sessionId || !currentSegment || isAudioGenerating) return;
    setIsAudioGenerating(true);
    try {
      const result = await storyService.generateAudioOnDemand(
        sessionId,
        currentSegment.segment_id,
      );
      setOnDemandAudioUrl(result.audio_url);
    } catch {
      // Silently fail - button will remain clickable
    } finally {
      setIsAudioGenerating(false);
    }
  }, [sessionId, currentSegment, isAudioGenerating]);

  // Trigger confetti on completion
  useEffect(() => {
    if (isCompleted) {
      triggerConfetti();
    }
  }, [isCompleted, triggerConfetti]);

  // Determine page state — show setup while resuming/validating
  const pageState: InteractiveStoryPageState = getInteractiveStoryPageState({
    isResuming,
    isCompleted,
    hasCurrentSegment: !!currentSegment,
  });

  // Toggle interest selection
  const toggleInterest = (interest: string) => {
    if (selectedInterests.includes(interest)) {
      setSelectedInterests(selectedInterests.filter((i) => i !== interest));
    } else if (selectedInterests.length < 5) {
      setSelectedInterests([...selectedInterests, interest]);
    }
  };

  // Start story handler - uses streaming for real-time progress
  const handleStartStory = async () => {
    if (!selectedAge || selectedInterests.length === 0 || !childId) return;

    try {
      await startStoryStream({
        child_id: childId,
        age_group: selectedAge,
        interests: selectedInterests,
        theme: theme || undefined,
        story_length: selectedLength,
      });
    } catch {
      // Error is handled by the hook
    }
  };

  // Choice handler - uses streaming for real-time progress
  const handleChoice = async (choiceId: string) => {
    // First in-page interaction unlocks audio auto-play (see
    // audioMaySelfStart above). Without this, a user who lands here
    // via a Content Hub share would never get audio even when they
    // wanted it on subsequent segments.
    setUserHasInteracted(true);
    try {
      await makeChoiceStream(choiceId);
    } catch {
      // Error is handled by the hook
    }
  };

  // Reset handler
  const handleReset = () => {
    reset();
    setSelectedAge(null);
    setSelectedLength("short");
    setSelectedInterests([]);
    setTheme("");
    setSessionExpiredMsg(null);
  };

  // Save interactive story to My Library
  const handleSaveStory = useCallback(async () => {
    if (!sessionId || saveStatus === "saving" || saveStatus === "saved") return;
    setSaveStatus("saving");
    try {
      await storyService.saveInteractiveStory(sessionId);
      setSaveStatus("saved");
    } catch {
      setSaveStatus("error");
    }
  }, [sessionId, saveStatus]);

  // Calculate total segments (estimate based on progress)
  const totalSegments =
    storyLengthMode === "unlimited"
      ? 0
      : progress > 0
        ? Math.round((choiceHistory.length + 1) / progress)
        : 5;

  // End story handler for unlimited mode
  const handleEndStory = async () => {
    try {
      await endStory();
    } catch {
      // Error is handled by the hook
    }
  };

  const renderStoryTimeline = () => (
    <div ref={chapterContainerRef} className="space-y-4">
      {segments.map((segment, index) => {
        const selectedChoiceId = choiceHistory[index];
        const segmentChoices = Array.isArray(segment.choices)
          ? segment.choices
          : [];
        const matchedChoice = selectedChoiceId
          ? segmentChoices.find(
              (choice) => choice.choice_id === selectedChoiceId,
            )
          : null;
        const selectedChoiceText = matchedChoice?.text || selectedChoiceId;
        return (
          <div
            key={`${segment.segment_id}-${index}`}
            data-chapter-index={index}
            className="space-y-3 scroll-mt-24"
          >
            <PerspectiveContainer enableTilt={false}>
              <StorySegmentDisplay
                segment={segment}
                title={storyTitle}
                segmentIndex={index}
                isRevealing={isRevealing && index === segments.length - 1}
              />
            </PerspectiveContainer>

            {selectedChoiceId && (
              <motion.div
                className="mx-auto max-w-md rounded-xl border border-primary/25 bg-primary/5 px-4 py-3 text-center"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
              >
                <p className="text-xs font-semibold uppercase tracking-wide text-primary mb-1">
                  You Chose
                </p>
                <p className="inline-flex items-center justify-center gap-1.5 text-sm text-gray-700">
                  <CheckCircle size={14} />
                  {selectedChoiceText}
                </p>
              </motion.div>
            )}
          </div>
        );
      })}
    </div>
  );

  const showChapterRail =
    (pageState === "playing" || pageState === "completed") &&
    segments.length >= 2;
  // For the breadcrumb pill, show the choice that led TO the active chapter
  // (i.e. the choice made at the previous chapter), since the active chapter
  // itself has no choice yet.
  const arrivingChoice =
    activeChapterIndex > 0
      ? choiceMetaAt(
          segments[activeChapterIndex - 1],
          choiceHistory[activeChapterIndex - 1],
        )
      : null;
  const lockedAfterIndex =
    storyLengthMode === "unlimited" && pageState === "playing"
      ? segments.length
      : null;

  return (
    <div className="lg:flex lg:gap-6 lg:items-start max-w-screen-xl mx-auto">
      {showChapterRail && (
        <ChapterRail
          segments={segments}
          choiceHistory={choiceHistory}
          activeIndex={activeChapterIndex}
          lockedAfterIndex={lockedAfterIndex}
          onJump={scrollToChapter}
          scrollProgress={scrollProgressMV}
        />
      )}

      <div className="flex-1 max-w-2xl mx-auto w-full space-y-6">
      {/* Header */}
      <motion.div
        className="text-center"
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <motion.span
          className="mx-auto inline-flex h-14 w-14 items-center justify-center rounded-lg bg-primary/10 text-primary"
          animate={{ rotate: [0, -5, 5, 0] }}
          transition={{ duration: 3, repeat: Infinity }}
        >
          <BookOpen size={30} />
        </motion.span>
        <h1 className="text-2xl md:text-3xl font-bold text-gray-800 mt-2">
          Interactive Story
        </h1>
        <p className="text-gray-600 mt-1">
          Choose your adventure, create unique story endings
        </p>

        {showChapterRail && (
          <motion.div
            className="mt-3 inline-flex lg:hidden items-center gap-2 rounded-full bg-primary/10 border border-primary/25 px-3 py-1 text-xs"
            key={activeChapterIndex}
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <span className="font-semibold text-primary">
              Chapter {activeChapterIndex + 1} of {segments.length}
            </span>
            {arrivingChoice ? (
              <span className="text-gray-600 truncate max-w-[18rem]">
                · arrived via {arrivingChoice.text}
              </span>
            ) : (
              <span className="text-gray-500">· beginning of story</span>
            )}
          </motion.div>
        )}
      </motion.div>

      {/* Quota exceeded overlay */}
      <QuotaExceededOverlay
        show={isQuotaError(error) && !quotaDismissed}
        message={error ?? ""}
        onDismiss={() => setQuotaDismissed(true)}
      />

      {/* Error display (non-quota errors) */}
      {error && !isQuotaError(error) && (
        <motion.div
          className="bg-red-50 border border-red-200 rounded-card p-4 text-red-700"
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
        >
          <div className="flex items-center gap-2">
            <XCircle size={18} />
            <span>{error}</span>
          </div>
        </motion.div>
      )}

      {/* Setup View */}
      {pageState === "setup" && (
        <motion.div
          className="space-y-6"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
        >
          {/* Session expired message */}
          {sessionExpiredMsg && (
            <motion.div
              className="bg-amber-50 border border-amber-200 rounded-2xl p-4 text-amber-700 text-sm text-center"
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
            >
              <Sunrise className="mr-1 inline" size={18} /> {sessionExpiredMsg}
            </motion.div>
          )}

          {/* Age Group Selection */}
          <Card>
            <h2 className="text-lg font-bold text-gray-800 mb-4 flex items-center gap-2">
              <UserRound size={20} />
              Select Age Group
              <span className="text-red-500">*</span>
            </h2>
            <div className="grid grid-cols-3 gap-3">
              {AGE_GROUPS.map((age) => {
                const Icon = age.icon
                return (
                  <motion.button
                    key={age.value}
                    className={`
                      p-4 rounded-xl border-2 text-center transition-colors
                      ${
                        selectedAge === age.value
                          ? "border-primary bg-primary/10"
                          : "border-gray-200 hover:border-primary/50"
                      }
                    `}
                    onClick={() => setSelectedAge(age.value)}
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                  >
                    <Icon className="mx-auto mb-1 text-gray-700" size={24} />
                    <span className="text-sm font-medium">{age.label}</span>
                  </motion.button>
                )
              })}
            </div>
          </Card>

          {/* Story Length Mode (#331) */}
          <Card>
            <h2 className="text-lg font-bold text-gray-800 mb-4 flex items-center gap-2">
              <Clock size={20} />
              Story Length
            </h2>
            <div className="grid grid-cols-3 gap-3">
              {STORY_LENGTHS.map((len) => {
                const Icon = len.icon
                return (
                  <motion.button
                    key={len.value}
                    className={`
                      p-4 rounded-xl border-2 text-center transition-colors
                      ${
                        selectedLength === len.value
                          ? "border-primary bg-primary/10"
                          : "border-gray-200 hover:border-primary/50"
                      }
                    `}
                    onClick={() => setSelectedLength(len.value)}
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                  >
                    <Icon className="mx-auto mb-1 text-gray-700" size={24} />
                    <span className="text-sm font-medium block">{len.label}</span>
                    <span className="text-xs text-gray-400">{len.sublabel}</span>
                  </motion.button>
                )
              })}
            </div>
          </Card>

          {/* Interest Tags */}
          <Card>
            <h2 className="text-lg font-bold text-gray-800 mb-2 flex items-center gap-2">
              <Sparkles size={20} />
              Select Interests
              <span className="text-sm font-normal text-gray-500">(1-5)</span>
            </h2>
            <p className="text-sm text-gray-500 mb-4">
              Selected {selectedInterests.length}/5
            </p>
            <div className="flex flex-wrap gap-2">
              {DEFAULT_INTERESTS.map((interest) => (
                <motion.button
                  key={interest}
                  className={`
                    px-4 py-2 rounded-full text-sm font-medium transition-colors
                    ${
                      selectedInterests.includes(interest)
                        ? "bg-secondary text-white"
                        : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                    }
                    ${
                      selectedInterests.length >= 5 &&
                      !selectedInterests.includes(interest)
                        ? "opacity-50 cursor-not-allowed"
                        : ""
                    }
                  `}
                  onClick={() => toggleInterest(interest)}
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  disabled={
                    selectedInterests.length >= 5 &&
                    !selectedInterests.includes(interest)
                  }
                >
                  {interest}
                </motion.button>
              ))}
            </div>
          </Card>

          {/* Theme Input */}
          <Card>
            <h2 className="text-lg font-bold text-gray-800 mb-4 flex items-center gap-2">
              <Palette size={20} />
              Story Theme
              <span className="text-sm font-normal text-gray-500">
                (Optional)
              </span>
            </h2>
            <input
              type="text"
              value={theme}
              onChange={(e) => setTheme(e.target.value)}
              placeholder="e.g., Finding lost treasure, Space adventure..."
              className="w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-primary focus:outline-none transition-colors"
              maxLength={50}
            />
            <div className="mt-4">
              <SuggestedThemes
                mode="prompt"
                limit={6}
                onSelect={(t) => setTheme(t)}
              />
            </div>
          </Card>

          {/* Enhanced Streaming Progress with 2.5D Visualizer */}
          {streaming.isStreaming && (
            <StreamingVisualizer
              phase={animationPhase}
              message={streaming.streamMessage || "Creating story..."}
              thinkingContent={streaming.thinkingContent}
              layout="card"
              showParticles={false}
              showSparkles
            />
          )}

          {/* Start Button */}
          <Button
            size="lg"
            className="w-full"
            onClick={handleStartStory}
            isLoading={isLoading}
            disabled={
              !selectedAge ||
              selectedInterests.length === 0 ||
              streaming.isStreaming
            }
            leftIcon={<Rocket size={18} />}
          >
            {streaming.isStreaming ? "Creating..." : "Start Story"}
          </Button>
        </motion.div>
      )}

      {/* Resume loading view */}
      {pageState === "resuming" && (
        <motion.div
          className="space-y-6"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
        >
          <Card>
            <StreamingVisualizer
              phase="connecting"
              message="Opening your story..."
              thinkingContent=""
              layout="card"
              showParticles={false}
              showSparkles
            />
          </Card>
        </motion.div>
      )}

      {/* Playing View */}
      {pageState === "playing" && currentSegment && (
        <motion.div
          className="space-y-6"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
        >
          {/* Progress */}
          <ProgressIndicator
            current={choiceHistory.length}
            total={totalSegments}
            choiceHistory={choiceHistory}
            storyLengthMode={storyLengthMode}
          />

          {/* Story Segment with age-aware content display */}
          <AgeAwareContent
            ageGroup={activeAgeGroup}
            audioUrl={currentSegment.audio_url || onDemandAudioUrl}
            onRequestAudio={handleRequestAudio}
            isAudioLoading={isAudioGenerating}
            autoPlayAudio={audioMaySelfStart}
            textContent={renderStoryTimeline()}
          />

          {/* Choices */}
          {!currentSegment.is_ending &&
            (currentSegment.choices?.length ?? 0) > 0 && (
              <div className="space-y-3">
                <h3 className="text-center text-gray-600 font-medium">
                  What happens next?
                </h3>
                <ChoiceButtons
                  choices={currentSegment.choices || []}
                  onChoose={handleChoice}
                  isLoading={isLoading}
                  disabled={isLoading}
                />
              </div>
            )}

          {/* End Story button for unlimited mode */}
          {storyLengthMode === "unlimited" &&
            !currentSegment.is_ending &&
            !isLoading && (
              <motion.div
                className="text-center"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.5 }}
              >
                <Button
                  variant="outline"
                  size="md"
                  onClick={handleEndStory}
                  disabled={isLoading}
                  leftIcon={<Flag size={18} />}
                >
                  End My Story
                </Button>
              </motion.div>
            )}

          {/* Loading overlay with streaming visualizer */}
          {isLoading && (
            <StreamingVisualizer
              phase={animationPhase}
              message={streaming.streamMessage || "Story is unfolding..."}
              thinkingContent={streaming.thinkingContent}
              layout="card"
              showSparkles
            />
          )}
        </motion.div>
      )}

      {/* Completed View */}
      {pageState === "completed" && (
        <motion.div
          className="space-y-6"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
        >
          {/* Full story journey with selected choices interleaved */}
          {currentSegment && (
            <AgeAwareContent
              ageGroup={activeAgeGroup}
              audioUrl={currentSegment.audio_url || onDemandAudioUrl}
              onRequestAudio={handleRequestAudio}
              isAudioLoading={isAudioGenerating}
              autoPlayAudio={audioMaySelfStart}
              textContent={renderStoryTimeline()}
            />
          )}

          {/* Educational Summary */}
          {educationalSummary && (
            <Card>
              <h3 className="text-lg font-bold text-gray-800 mb-4 flex items-center gap-2">
                <Library size={20} />
                What You Learned
              </h3>
              <EducationalTags value={educationalSummary} />
            </Card>
          )}

          {/* Journey summary */}
          <Card variant="colorful" colorScheme="accent">
            <div className="text-center">
              <Trophy className="mx-auto mb-2 text-yellow-600" size={36} />
              <h3 className="text-lg font-bold text-gray-800 mb-1">
                You completed this story!
              </h3>
              <p className="text-gray-600 text-sm">
                Made {choiceHistory.length} choices
              </p>
            </div>
          </Card>

          {/* Action buttons */}
          <div className="flex flex-col sm:flex-row gap-3">
            <Button
              variant="secondary"
              size="lg"
              className="flex-1"
              onClick={handleSaveStory}
              disabled={saveStatus === "saving" || saveStatus === "saved"}
              isLoading={saveStatus === "saving"}
              leftIcon={saveStatus === "saved" ? <CheckCircle size={18} /> : <Save size={18} />}
            >
              {saveStatus === "saved"
                ? "Saved!"
                : saveStatus === "error"
                  ? "Retry Save"
                  : "Save to My Library"}
            </Button>
            <Button
              variant="primary"
              size="lg"
              className="flex-1"
              onClick={handleReset}
              leftIcon={<RotateCcw size={18} />}
            >
              Play Again
            </Button>
            <Button
              variant="outline"
              size="lg"
              className="flex-1"
              onClick={() => navigate("/")}
              leftIcon={<Home size={18} />}
            >
              Back to Home
            </Button>
          </div>

          {/* Share-to-Content-Hub CTA (#453) — pink-faded shared style */}
          {sessionId && (
            <div className="flex justify-center pt-2">
              <button
                type="button"
                className="rounded-2xl bg-gradient-to-r from-rose-300 via-pink-300 to-rose-300 hover:from-rose-400 hover:via-pink-400 hover:to-rose-400 px-6 py-3 text-base font-bold text-white shadow-md hover:shadow-lg transition-all"
                onClick={() => setShareOpen(true)}
              >
                <span className="inline-flex items-center gap-2">
                  <Globe2 size={18} />
                  Share to Content Hub
                </span>
              </button>
            </div>
          )}
        </motion.div>
      )}
      </div>

      {sessionId && (
        <ShareToHubModal
          open={shareOpen}
          onClose={() => setShareOpen(false)}
          source={{
            artifact_type: "interactive_story",
            source_id: sessionId,
          }}
        />
      )}
    </div>
  );
}

function InteractiveStoryPage() {
  const { isAuthenticated } = useAuthStore();

  if (!isAuthenticated) {
    return (
      <div className="max-w-lg mx-auto mt-12">
        <LoginPrompt feature="play interactive stories" />
      </div>
    );
  }

  return <InteractiveStoryPageContent />;
}

export default InteractiveStoryPage;

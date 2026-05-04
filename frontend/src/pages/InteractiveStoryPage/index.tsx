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
import LoginPrompt from "@/components/common/LoginPrompt";
import SuggestedThemes from "@/components/common/SuggestedThemes";

type PageState = "setup" | "playing" | "completed";

const AGE_GROUPS: { value: AgeGroup; label: string; emoji: string }[] = [
  { value: "3-5", label: "3-5 yrs", emoji: "🧒" },
  { value: "6-8", label: "6-8 yrs", emoji: "👦" },
  { value: "9-12", label: "9-12 yrs", emoji: "🧑" },
];

const STORY_LENGTHS: {
  value: StoryLengthMode;
  label: string;
  sublabel: string;
  emoji: string;
}[] = [
  { value: "short", label: "Quick Tale", sublabel: "5 choices", emoji: "📖" },
  { value: "medium", label: "Short Story", sublabel: "10 choices", emoji: "📚" },
  { value: "unlimited", label: "Endless Adventure", sublabel: "No limit", emoji: "🌟" },
];

function InteractiveStoryPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { isAuthenticated } = useAuthStore();
  const { defaultChildId } = useChildStore();

  if (!isAuthenticated) {
    return (
      <div className="max-w-lg mx-auto mt-12">
        <LoginPrompt feature="play interactive stories" />
      </div>
    );
  }

  // Local form state
  const [selectedAge, setSelectedAge] = useState<AgeGroup | null>(null);
  const [selectedLength, setSelectedLength] = useState<StoryLengthMode>("short");
  const [selectedInterests, setSelectedInterests] = useState<string[]>([]);
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

  // Resume only when URL contains ?session=
  const [isResuming, setIsResuming] = useState(false);
  const [sessionExpiredMsg, setSessionExpiredMsg] = useState<string | null>(
    null,
  );
  const sessionParam = searchParams.get("session");

  useEffect(() => {
    // Explicit resume path: /interactive?session=...
    if (sessionParam) {
      let cancelled = false;
      setIsResuming(true);
      setSessionExpiredMsg(null);
      resumeSession(sessionParam)
        .catch(() => {
          reset();
          if (!cancelled) {
            setSessionExpiredMsg("This story is no longer available. Please start a new story.");
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
  }, [currentSegment?.segment_id, streaming.isStreaming]);

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
  const getPageState = (): PageState => {
    if (isResuming) return "setup";
    if (isCompleted) return "completed";
    if (currentSegment) return "playing";
    return "setup";
  };

  const pageState = getPageState();

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
    if (!selectedAge || selectedInterests.length === 0) return;

    try {
      await startStoryStream({
        child_id: defaultChildId,
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
        const selectedChoiceEmoji = matchedChoice?.emoji || "✅";

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
                <p className="text-sm text-gray-700">
                  <span className="mr-1">{selectedChoiceEmoji}</span>
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
          className="text-5xl inline-block"
          animate={{ rotate: [0, -5, 5, 0] }}
          transition={{ duration: 3, repeat: Infinity }}
        >
          🎭
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
                · arrived via {arrivingChoice.emoji} {arrivingChoice.text}
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
            <span>❌</span>
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
              <span className="text-lg mr-1">🌅</span> {sessionExpiredMsg}
            </motion.div>
          )}

          {/* Age Group Selection */}
          <Card>
            <h2 className="text-lg font-bold text-gray-800 mb-4 flex items-center gap-2">
              <span>👶</span>
              Select Age Group
              <span className="text-red-500">*</span>
            </h2>
            <div className="grid grid-cols-3 gap-3">
              {AGE_GROUPS.map((age) => (
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
                  <span className="text-2xl block mb-1">{age.emoji}</span>
                  <span className="text-sm font-medium">{age.label}</span>
                </motion.button>
              ))}
            </div>
          </Card>

          {/* Story Length Mode (#331) */}
          <Card>
            <h2 className="text-lg font-bold text-gray-800 mb-4 flex items-center gap-2">
              <span>⏱️</span>
              Story Length
            </h2>
            <div className="grid grid-cols-3 gap-3">
              {STORY_LENGTHS.map((len) => (
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
                  <span className="text-2xl block mb-1">{len.emoji}</span>
                  <span className="text-sm font-medium block">{len.label}</span>
                  <span className="text-xs text-gray-400">{len.sublabel}</span>
                </motion.button>
              ))}
            </div>
          </Card>

          {/* Interest Tags */}
          <Card>
            <h2 className="text-lg font-bold text-gray-800 mb-2 flex items-center gap-2">
              <span>💫</span>
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
              <span>🎨</span>
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
            leftIcon={<span>🚀</span>}
          >
            {streaming.isStreaming ? "Creating..." : "Start Story"}
          </Button>
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
            autoPlayAudio={activeAgeGroup === "3-5"}
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
                  leftIcon={<span>🏁</span>}
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
              autoPlayAudio={activeAgeGroup === "3-5"}
              textContent={renderStoryTimeline()}
            />
          )}

          {/* Educational Summary */}
          {educationalSummary && (
            <Card>
              <h3 className="text-lg font-bold text-gray-800 mb-4 flex items-center gap-2">
                <span>📚</span>
                What You Learned
              </h3>
              <EducationalTags value={educationalSummary} />
            </Card>
          )}

          {/* Journey summary */}
          <Card variant="colorful" colorScheme="accent">
            <div className="text-center">
              <span className="text-4xl block mb-2">🏆</span>
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
              leftIcon={<span>{saveStatus === "saved" ? "✅" : "💾"}</span>}
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
              leftIcon={<span>🔄</span>}
            >
              Play Again
            </Button>
            <Button
              variant="outline"
              size="lg"
              className="flex-1"
              onClick={() => navigate("/")}
              leftIcon={<span>🏠</span>}
            >
              Back to Home
            </Button>
          </div>
        </motion.div>
      )}
      </div>
    </div>
  );
}

export default InteractiveStoryPage;

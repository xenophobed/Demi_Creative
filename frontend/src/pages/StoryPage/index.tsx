import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  BookOpen,
  Film,
  Frown,
  Globe2,
  Library,
  PartyPopper,
  Sparkles,
} from "lucide-react";
import Button from "@/components/common/Button";
import Loading from "@/components/common/Loading";
import AgeAwareContent from "@/components/common/AgeAwareContent";
import BookContainer from "@/components/story/BookContainer";
import DynamicPictureBook from "@/components/story/DynamicPictureBook";
import StoryDisplay from "@/components/story/StoryDisplay";
import TabbedMetadata from "@/components/story/TabbedMetadata";
import useStoryStore from "@/store/useStoryStore";
import useChildStore from "@/store/useChildStore";
import useAuthStore from "@/store/useAuthStore";
import storyService from "@/api/services/storyService";
import videoService from "@/api/services/videoService";
import type { StoryVideosResponse, VideoStatus } from "@/types/api";
import { resolveMediaUrl } from "@/utils/mediaUrl";
import ShareToHubModal from "@/components/hub/ShareToHubModal";

export type StoryVideoUiState =
  | "idle"
  | "queued"
  | "generating"
  | "completed"
  | "failed";

export function applyProviderStatusToStoryVideo(
  status: VideoStatus,
): StoryVideoUiState {
  if (status === "pending") return "queued";
  if (status === "processing") return "generating";
  if (status === "completed") return "completed";
  return "failed";
}

export function getStoryVideoStatusMessage(status: StoryVideoUiState): string {
  if (status === "queued") return "Queued for video magic";
  if (status === "generating") return "Making your story video";
  if (status === "completed") return "Your video is ready";
  if (status === "failed") return "Video is not available right now";
  return "";
}

export function shouldRenderPictureBookFallback(
  userRequestedFallback: boolean,
  videoStatus: StoryVideoUiState,
): boolean {
  return userRequestedFallback || videoStatus === "failed";
}

export function findLatestCompletedStoryVideoUrl(
  response: StoryVideosResponse | undefined,
): string | null {
  const completed = [...(response?.videos ?? [])]
    .filter((video) => video.status === "completed" && video.video_url)
    .sort((a, b) => {
      const left = a.created_at ? Date.parse(a.created_at) : 0;
      const right = b.created_at ? Date.parse(b.created_at) : 0;
      return right - left;
    });

  return completed[0]?.video_url ?? null;
}

function deriveStoryTitleFromText(storyText: string | undefined): string {
  if (!storyText) return "Your Story";

  const firstLine =
    storyText
      .split("\n")
      .map((line) => line.trim())
      .find(Boolean) || "";

  const cleaned = firstLine.replace(/^[《「『【〈\s]+|[》」』】〉\s]+$/g, "");
  const firstClause =
    cleaned
      .split(/[。！？.!?；;:：]/)
      .map((s) => s.trim())
      .find(Boolean) || cleaned;

  const normalized =
    firstClause.replace(/^once upon a time[,\s]*/i, "").trim() || firstClause;
  const hasCjk = /[\u4e00-\u9fff]/.test(normalized);
  const maxLen = hasCjk ? 12 : 22;

  if (normalized.length <= maxLen) return normalized;
  return `${normalized.slice(0, maxLen)}...`;
}

function StoryPage() {
  const { storyId } = useParams<{ storyId: string }>();
  const navigate = useNavigate();

  const {
    currentStory,
    setCurrentStory,
    reset,
    justGenerated,
    setJustGenerated,
  } = useStoryStore();
  const { currentChild } = useChildStore();
  const { isAuthenticated, user } = useAuthStore();

  // Show banner only when navigating directly from the upload/generation flow
  const [showBanner, setShowBanner] = useState(false);
  // Share-to-Content-Hub modal (#453)
  const [shareOpen, setShareOpen] = useState(false);

  useEffect(() => {
    if (justGenerated) {
      setShowBanner(true);
      setJustGenerated(false); // clear from store immediately so re-mounts don't re-show
    }
  }, [justGenerated, setJustGenerated]);

  // On-demand audio state (for 9-12 age group)
  const [onDemandAudioUrl, setOnDemandAudioUrl] = useState<string | null>(null);
  const [isAudioGenerating, setIsAudioGenerating] = useState(false);
  const [videoJobId, setVideoJobId] = useState<string | null>(null);
  const [videoStatus, setVideoStatus] = useState<StoryVideoUiState>("idle");
  const [videoProgress, setVideoProgress] = useState(0);
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [videoError, setVideoError] = useState<string | null>(null);
  const [showPictureBook, setShowPictureBook] = useState(false);

  // Only use currentStory if it matches the URL's storyId
  const currentUserId = user?.user_id ?? "anonymous";
  const matchingStory =
    !isAuthenticated && currentStory?.story_id === storyId ? currentStory : null;

  // If store doesn't have the matching story, fetch from API
  const {
    data: fetchedStory,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["story", currentUserId, storyId],
    queryFn: () => storyService.getStory(storyId!),
    enabled: !matchingStory && !!storyId,
    retry: 1,
  });

  // Use matching store story or fetched story
  const story = matchingStory || fetchedStory;

  // If API returned a story, save to store
  useEffect(() => {
    if (fetchedStory && !matchingStory) {
      setCurrentStory(fetchedStory);
    }
  }, [fetchedStory, matchingStory, setCurrentStory]);

  // On-demand audio handler for 9-12 age group
  const handleRequestAudio = useCallback(async () => {
    if (!story || isAudioGenerating) return;
    setIsAudioGenerating(true);
    try {
      const result = await storyService.generateAudioForStory(story.story_id);
      setOnDemandAudioUrl(result.audio_url);
    } catch {
      // Silently fail - button will remain clickable
    } finally {
      setIsAudioGenerating(false);
    }
  }, [story, isAudioGenerating]);

  const { data: storyVideos } = useQuery({
    queryKey: ["story-videos", story?.story_id],
    queryFn: () => videoService.getVideosByStory(story!.story_id),
    enabled: isAuthenticated && !!story?.story_id,
    retry: 1,
  });

  useEffect(() => {
    if (videoStatus !== "idle") return;

    const completedVideoUrl = findLatestCompletedStoryVideoUrl(storyVideos);
    if (!completedVideoUrl) return;

    setVideoStatus("completed");
    setVideoProgress(100);
    setVideoUrl(resolveMediaUrl(completedVideoUrl));
    setVideoError(null);
  }, [storyVideos, videoStatus]);

  const handleStartVideo = useCallback(async () => {
    if (!story || videoStatus === "queued" || videoStatus === "generating") return;

    setVideoStatus("queued");
    setVideoProgress(0);
    setVideoUrl(null);
    setVideoError(null);
    setShowPictureBook(false);

    try {
      const result = await videoService.generateVideo({
        story_id: story.story_id,
        style: "storybook",
        include_audio: Boolean(story.audio_url || onDemandAudioUrl),
        duration_seconds: 10,
      });

      setVideoJobId(result.job_id);
      setVideoStatus(applyProviderStatusToStoryVideo(result.status));

      if (result.status === "completed") {
        const completed = await videoService.getVideoStatus(result.job_id);
        setVideoProgress(completed.progress_percent ?? 100);
        setVideoError(completed.error_message ?? null);
        if (completed.video_url) {
          setVideoUrl(resolveMediaUrl(completed.video_url));
        }
      }
    } catch (err) {
      const message =
        err instanceof Error
          ? err.message
          : "Video generation is unavailable right now.";
      setVideoJobId(null);
      setVideoStatus("failed");
      setVideoError(message);
      setShowPictureBook(true);
    }
  }, [onDemandAudioUrl, story, videoStatus]);

  useEffect(() => {
    if (!videoJobId || !["queued", "generating"].includes(videoStatus)) return;

    let cancelled = false;
    const poll = async () => {
      try {
        const result = await videoService.getVideoStatus(videoJobId);
        if (cancelled) return;

        const nextStatus = applyProviderStatusToStoryVideo(result.status);
        setVideoStatus(nextStatus);
        setVideoProgress(result.progress_percent ?? 0);
        setVideoError(result.error_message ?? null);
        if (result.video_url) {
          setVideoUrl(resolveMediaUrl(result.video_url));
        }
        if (nextStatus === "failed") {
          setShowPictureBook(true);
        }
      } catch (err) {
        if (cancelled) return;
        const message =
          err instanceof Error
            ? err.message
            : "We could not check the video status.";
        setVideoStatus("failed");
        setVideoError(message);
        setShowPictureBook(true);
      }
    };

    void poll();
    const interval = window.setInterval(poll, 5000);

    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [videoJobId, videoStatus]);

  const handleNewStory = () => {
    reset();
    navigate("/upload");
  };

  const isForbidden =
    (error as { response?: { status?: number } } | null)?.response?.status === 403;

  // Loading state
  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loading size="lg" message="Loading your story..." />
      </div>
    );
  }

  // Error state
  if (error || !story) {
    return (
      <div className="text-center py-16">
        <motion.div
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          className="mb-4 flex justify-center"
        >
          <Frown className="h-16 w-16 text-gray-400" strokeWidth={2} />
        </motion.div>
        <h2 className="text-xl font-bold text-gray-800 mb-2">
          {isForbidden ? "Story not available for this account" : "Story not found"}
        </h2>
        <p className="text-gray-500 mb-6">
          {isForbidden
            ? "You are signed in as a different user than the one who created this story."
            : "This story may have expired or doesn't exist"}
        </p>
        <Link to="/upload">
          <Button>Create New Story</Button>
        </Link>
      </div>
    );
  }

  const originalImageUrl = resolveMediaUrl(story.image_url);
  const styledImageUrl = resolveMediaUrl(
    story.styled_image_url || story.cover_image_url,
  );
  const imageUrl = styledImageUrl || originalImageUrl;
  const storyTitle = deriveStoryTitleFromText(story.story.text);
  // Use the story's age_group (content was generated for it), fall back to child store
  const ageGroup = story.age_group || currentChild?.age_group || null;

  return (
    <motion.div
      className="story-page"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
    >
      {/* Header with back button */}
      <motion.header
        className="story-page-header"
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <button
          onClick={() => navigate(-1)}
          className="back-button"
          aria-label="Go back"
        >
          <span>←</span>
          <span>Back</span>
        </button>

        <h1 className="page-title flex-1 min-w-0">{storyTitle}</h1>

        {/* Empty spacer to maintain layout */}
        <div className="w-10" />
      </motion.header>

      {/* Success notification — only shown when navigating from the generation flow */}
      {showBanner && (
        <motion.div
          className="success-banner"
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <motion.span
            className="inline-flex text-primary"
            animate={{ scale: [1, 1.2, 1] }}
            transition={{ duration: 0.5 }}
          >
            <PartyPopper className="h-6 w-6" />
          </motion.span>
          <div>
            <p className="font-bold text-gray-800">
              Story created successfully!
            </p>
            <p className="text-sm text-gray-600">
              AI crafted this unique story from your artwork
            </p>
          </div>
        </motion.div>
      )}

      {/* Book container with story - age-aware display */}
      <AgeAwareContent
        ageGroup={ageGroup}
        audioUrl={
          story.audio_url
            ? resolveMediaUrl(story.audio_url)
            : resolveMediaUrl(onDemandAudioUrl)
        }
        onRequestAudio={handleRequestAudio}
        isAudioLoading={isAudioGenerating}
        autoPlayAudio={ageGroup === "3-5"}
        textContent={
          <BookContainer>
            <StoryDisplay
              story={story.story}
              title={storyTitle || `Story #${story.story_id.slice(0, 6)}`}
              imageUrl={imageUrl}
              originalImageUrl={originalImageUrl}
              styledImageUrl={styledImageUrl}
            />
          </BookContainer>
        }
      />

      <motion.section
        className="story-video-panel"
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        aria-label="Story video generation"
      >
        <div className="story-video-panel-copy">
          <p className="story-video-eyebrow">Story movie</p>
          <h2>Turn this story into a little video</h2>
        </div>

        <div className="story-video-actions">
          <Button
            variant="secondary"
            size="md"
            onClick={handleStartVideo}
            isLoading={videoStatus === "queued" || videoStatus === "generating"}
            leftIcon={<Film size={18} aria-hidden="true" />}
          >
            {videoStatus === "completed" ? "Make Again" : "Make Video"}
          </Button>
          <Button
            variant="outline"
            size="md"
            onClick={() => setShowPictureBook((current) => !current)}
            leftIcon={<BookOpen size={18} aria-hidden="true" />}
          >
            {showPictureBook ? "Hide Picture Book" : "Picture Book"}
          </Button>
        </div>

        {videoStatus !== "idle" && (
          <div className={`story-video-status ${videoStatus}`} role="status">
            <span>
              {getStoryVideoStatusMessage(videoStatus)}
            </span>
            {(videoStatus === "queued" || videoStatus === "generating") && (
              <div
                className="story-video-progress"
                aria-label={`Video generation ${videoProgress}% complete`}
              >
                <div style={{ width: `${Math.max(videoProgress, 8)}%` }} />
              </div>
            )}
            {videoError && <p>{videoError}</p>}
            {videoStatus === "failed" && (
              <button type="button" onClick={() => setShowPictureBook(true)}>
                Open picture-book mode
              </button>
            )}
          </div>
        )}

        {videoStatus === "completed" && videoUrl && (
          <video
            className="story-video-player"
            src={videoUrl}
            controls
            playsInline
            preload="metadata"
          />
        )}

        {shouldRenderPictureBookFallback(showPictureBook, videoStatus) && (
          <DynamicPictureBook
            story={story.story}
            title={storyTitle || `Story #${story.story_id.slice(0, 6)}`}
            imageUrl={imageUrl}
          />
        )}
      </motion.section>

      {/* Tabbed metadata section */}
      <TabbedMetadata
        characters={story.characters}
        educationalValue={story.educational_value}
        analysis={story.analysis}
        safetyScore={story.safety_score}
      />

      {/* Action buttons */}
      <motion.div
        className="action-buttons"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
      >
        <Button
          variant="primary"
          size="lg"
          className="flex-1"
          onClick={handleNewStory}
          leftIcon={<Sparkles size={18} />}
        >
          Create New Story
        </Button>
        <Button
          variant="outline"
          size="lg"
          className="flex-1"
          onClick={() => navigate("/library")}
          leftIcon={<Library size={18} />}
        >
          My Library
        </Button>
      </motion.div>

      {/* Share prompt + Share to Content Hub CTA (#453) */}
      <motion.div
        className="share-prompt flex flex-col items-center gap-3"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.5 }}
      >
        <p>Love this story? Share it with your family!</p>
        {storyId && (
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
        )}
      </motion.div>

      {storyId && (
        <ShareToHubModal
          open={shareOpen}
          onClose={() => setShareOpen(false)}
          source={{ artifact_type: "art_story", source_id: storyId }}
        />
      )}
    </motion.div>
  );
}

export default StoryPage;

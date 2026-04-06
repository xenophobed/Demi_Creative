import { useState, useCallback } from "react";
import { storyService } from "@/api/services/storyService";
import useInteractiveStoryStore from "@/store/useInteractiveStoryStore";
import { interactiveStoryGenerationManager } from "@/services/interactiveStoryGenerationManager";
import type {
  AgeGroup,
  InteractiveStoryStartRequest,
  StorySegment,
  EducationalValue,
} from "@/types/api";

interface StreamingState {
  isStreaming: boolean;
  streamStatus: string;
  streamMessage: string;
  thinkingContent: string;
  currentTurn: number;
}

interface UseInteractiveStoryReturn {
  // State
  sessionId: string | null;
  storyTitle: string;
  ageGroup: AgeGroup | null;
  currentSegment: StorySegment | null;
  segments: StorySegment[];
  choiceHistory: string[];
  progress: number;
  isLoading: boolean;
  error: string | null;
  isCompleted: boolean;
  educationalSummary: EducationalValue | null;

  // Streaming state
  streaming: StreamingState;

  // Actions
  startStory: (params: InteractiveStoryStartRequest) => Promise<void>;
  startStoryStream: (params: InteractiveStoryStartRequest) => Promise<void>;
  makeChoice: (choiceId: string) => Promise<void>;
  makeChoiceStream: (choiceId: string) => Promise<void>;
  resumeSession: (sessionId: string) => Promise<void>;
  reset: () => void;
}

export function useInteractiveStory(): UseInteractiveStoryReturn {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const {
    sessionId,
    storyTitle,
    ageGroup,
    currentSegment,
    segments,
    choiceHistory,
    progress,
    status,
    educationalSummary,
    streaming,
    setSession,
    addSegment,
    restoreSession,
    complete,
    setAgeGroup,
    reset: resetStore,
  } = useInteractiveStoryStore();

  const startStory = useCallback(
    async (params: InteractiveStoryStartRequest) => {
      setIsLoading(true);
      setError(null);
      setAgeGroup(params.age_group);

      try {
        const response = await storyService.startInteractiveStory(params);
        setSession(response, params.age_group);
      } catch (err) {
        const message =
          err instanceof Error
            ? err.message
            : "Failed to start story, please try again";
        setError(message);
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    [setSession, setAgeGroup],
  );

  const startStoryStream = useCallback(
    async (params: InteractiveStoryStartRequest) => {
      setError(null);
      setAgeGroup(params.age_group);

      try {
        await interactiveStoryGenerationManager.startStory(params);
      } catch (err) {
        const message =
          err instanceof Error
            ? err.message
            : "Failed to start story, please try again";
        setError(message);
        throw err;
      }
    },
    [setAgeGroup],
  );

  const makeChoice = useCallback(
    async (choiceId: string) => {
      if (!sessionId) {
        setError("Session not found");
        return;
      }

      setIsLoading(true);
      setError(null);

      try {
        const response = await storyService.makeChoice(sessionId, {
          choice_id: choiceId,
        });

        addSegment(response);

        // Check if this is the ending
        if (response.next_segment.is_ending) {
          // Fetch educational summary from session status
          try {
            const statusResponse =
              await storyService.getSessionStatus(sessionId);
            if (statusResponse.educational_summary) {
              complete(statusResponse.educational_summary);
            } else {
              // Create a default summary if none provided
              complete({
                themes: [],
                concepts: [],
                moral: undefined,
              });
            }
          } catch {
            // Complete without summary if status fetch fails
            complete({
              themes: [],
              concepts: [],
              moral: undefined,
            });
          }
        }
      } catch (err) {
        const message =
          err instanceof Error
            ? err.message
            : "Choice failed, please try again";
        setError(message);
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    [sessionId, addSegment, complete],
  );

  const makeChoiceStream = useCallback(
    async (choiceId: string) => {
      if (!sessionId) {
        setError("Session not found");
        return;
      }

      setError(null);

      try {
        await interactiveStoryGenerationManager.makeChoice(sessionId, choiceId);
      } catch (err) {
        const message =
          err instanceof Error
            ? err.message
            : "Choice failed, please try again";
        setError(message);
        throw err;
      }
    },
    [sessionId],
  );

  const resumeSession = useCallback(
    async (resumeSessionId: string) => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await storyService.resumeSession(resumeSessionId);
        restoreSession(response);
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Failed to resume story";
        setError(message);
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    [restoreSession],
  );

  const reset = useCallback(() => {
    resetStore();
    setError(null);
  }, [resetStore]);

  return {
    sessionId,
    storyTitle,
    ageGroup,
    currentSegment,
    segments,
    choiceHistory,
    progress,
    isLoading: isLoading || streaming.isStreaming,
    error,
    isCompleted: status === "completed",
    educationalSummary,
    streaming,
    startStory,
    startStoryStream,
    makeChoice,
    makeChoiceStream,
    resumeSession,
    reset,
  };
}

export default useInteractiveStory;

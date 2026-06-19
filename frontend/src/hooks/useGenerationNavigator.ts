import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { storyGenerationManager } from "@/services/storyGenerationManager";
import { interactiveStoryGenerationManager } from "@/services/interactiveStoryGenerationManager";
import { kidsDailyGenerationManager } from "@/services/kidsDailyGenerationManager";

/**
 * Registers React Router's navigate function with the generation manager
 * so it can navigate after generation completes, even if the user is on
 * a different page. Call once in PageContainer.
 */
export function useGenerationNavigator() {
  const navigate = useNavigate();

  useEffect(() => {
    storyGenerationManager.registerNavigate(navigate);
    interactiveStoryGenerationManager.registerNavigate(navigate);
    kidsDailyGenerationManager.registerNavigate(navigate);
  }, [navigate]);
}

export default useGenerationNavigator;

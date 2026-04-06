import { useLocation, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import useStoryStore from "@/store/useStoryStore";
import { storyGenerationManager } from "@/services/storyGenerationManager";
import useInteractiveStoryStore from "@/store/useInteractiveStoryStore";
import { interactiveStoryGenerationManager } from "@/services/interactiveStoryGenerationManager";

function GenerationStatusBar() {
  const location = useLocation();
  const navigate = useNavigate();
  const { generationInProgress, streaming: storyStreaming } = useStoryStore();
  const { streaming: interactiveStreaming, sessionId } =
    useInteractiveStoryStore();

  // Hide on /upload — that page has its own full visualizer
  const isOnUploadPage = location.pathname === "/upload";
  const isOnInteractivePage = location.pathname === "/interactive";

  const activeGeneration = generationInProgress
    ? "image"
    : interactiveStreaming.isStreaming
      ? "interactive"
      : null;

  const visible = Boolean(
    activeGeneration &&
    !(
      (activeGeneration === "image" && isOnUploadPage) ||
      (activeGeneration === "interactive" && isOnInteractivePage)
    ),
  );

  const message =
    activeGeneration === "interactive"
      ? interactiveStreaming.streamMessage ||
        "Crafting your interactive story..."
      : storyStreaming.streamMessage || "Generating your story...";

  const handleViewProgress = () => {
    if (activeGeneration === "interactive") {
      navigate(
        sessionId ? `/interactive?session=${sessionId}` : "/interactive",
      );
      return;
    }
    navigate("/upload");
  };

  const handleCancel = () => {
    if (activeGeneration === "interactive") {
      interactiveStoryGenerationManager.cancelGeneration();
      return;
    }
    storyGenerationManager.cancelGeneration();
  };

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          className="bg-gradient-to-r from-purple-500/90 to-pink-500/90 backdrop-blur-sm text-white shadow-md relative z-30"
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: "auto", opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          transition={{ duration: 0.3 }}
        >
          <div className="max-w-4xl mx-auto px-4 py-2 flex items-center justify-between gap-3">
            {/* Animated indicator + message */}
            <div className="flex items-center gap-3 min-w-0">
              <motion.span
                className="text-lg flex-shrink-0"
                animate={{ rotate: [0, 360] }}
                transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
              >
                ✨
              </motion.span>
              <span className="text-sm font-medium truncate">{message}</span>
            </div>

            {/* Action buttons */}
            <div className="flex items-center gap-2 flex-shrink-0">
              <button
                onClick={handleViewProgress}
                className="text-xs px-3 py-1 rounded-full bg-white/20 hover:bg-white/30 transition-colors font-medium"
              >
                View Progress
              </button>
              <button
                onClick={handleCancel}
                className="text-xs px-3 py-1 rounded-full bg-white/10 hover:bg-red-500/50 transition-colors font-medium"
              >
                Cancel
              </button>
            </div>
          </div>

          {/* Progress bar animation */}
          <motion.div
            className="h-0.5 bg-white/30"
            initial={{ scaleX: 0 }}
            animate={{ scaleX: 1 }}
            transition={{ duration: 60, ease: "linear" }}
            style={{ transformOrigin: "left" }}
          />
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export default GenerationStatusBar;

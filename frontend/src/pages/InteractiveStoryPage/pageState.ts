export type InteractiveStoryPageState =
  | "setup"
  | "resuming"
  | "playing"
  | "completed";

export function getInteractiveStoryPageState(params: {
  isResuming: boolean;
  isCompleted: boolean;
  hasCurrentSegment: boolean;
}): InteractiveStoryPageState {
  if (params.isResuming) return "resuming";
  if (params.isCompleted) return "completed";
  if (params.hasCurrentSegment) return "playing";
  return "setup";
}

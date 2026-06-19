import { afterEach, describe, expect, it, vi } from "vitest";
import { kidsDailyGenerationManager } from "../kidsDailyGenerationManager";
import useKidsDailyGenerationStore from "@/store/useKidsDailyGenerationStore";

afterEach(() => {
  // Leave no controller / progress armed between cases.
  kidsDailyGenerationManager.cancel();
});

describe("kidsDailyGenerationManager (#727)", () => {
  it("beginGeneration arms a fresh signal and reports generating via the store", () => {
    useKidsDailyGenerationStore.getState().begin("science", "Joining...");
    const signal = kidsDailyGenerationManager.beginGeneration();
    expect(signal.aborted).toBe(false);
    expect(kidsDailyGenerationManager.isGenerating()).toBe(true);
    expect(kidsDailyGenerationManager.isCurrent(signal)).toBe(true);
  });

  it("a second beginGeneration supersedes (aborts) the prior run", () => {
    const first = kidsDailyGenerationManager.beginGeneration();
    const second = kidsDailyGenerationManager.beginGeneration();
    expect(first.aborted).toBe(true);
    expect(second.aborted).toBe(false);
    expect(kidsDailyGenerationManager.isCurrent(first)).toBe(false);
    expect(kidsDailyGenerationManager.isCurrent(second)).toBe(true);
  });

  it("finish clears progress only for the owning signal", () => {
    useKidsDailyGenerationStore.getState().begin("science", "Joining...");
    const stale = kidsDailyGenerationManager.beginGeneration();
    const fresh = kidsDailyGenerationManager.beginGeneration();
    // A late finally from the superseded run must not wipe the fresh run.
    kidsDailyGenerationManager.finish(stale);
    expect(useKidsDailyGenerationStore.getState().generatingTopic).toBe(
      "science",
    );
    kidsDailyGenerationManager.finish(fresh);
    expect(useKidsDailyGenerationStore.getState().generatingTopic).toBeNull();
  });

  it("cancel aborts the active run and clears progress", () => {
    useKidsDailyGenerationStore.getState().begin("animals", "Joining...");
    const signal = kidsDailyGenerationManager.beginGeneration();
    kidsDailyGenerationManager.cancel();
    expect(signal.aborted).toBe(true);
    expect(useKidsDailyGenerationStore.getState().generatingTopic).toBeNull();
    expect(kidsDailyGenerationManager.isGenerating()).toBe(false);
  });

  it("queues completion navigation until a navigate fn registers", () => {
    const navigate = vi.fn();
    // No navigate registered yet → queued.
    kidsDailyGenerationManager.navigateToEpisode("/kids-daily/ep_1");
    expect(navigate).not.toHaveBeenCalled();
    // Registering flushes the pending path exactly once.
    kidsDailyGenerationManager.registerNavigate(navigate);
    expect(navigate).toHaveBeenCalledWith("/kids-daily/ep_1");
    // A subsequent completion navigates immediately.
    kidsDailyGenerationManager.navigateToEpisode("/kids-daily/ep_2");
    expect(navigate).toHaveBeenCalledWith("/kids-daily/ep_2");
    expect(navigate).toHaveBeenCalledTimes(2);
  });
});

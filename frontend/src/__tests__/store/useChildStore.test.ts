/* @vitest-environment node */

import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import type { ChildProfile } from "../../types/api";

vi.mock("@/api/services/childProfileService", () => ({
  childProfileService: {
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    archive: vi.fn(),
    setDefault: vi.fn(),
  },
}));

type ChildStore = typeof import("../../store/useChildStore").default;
type ChildProfileService =
  typeof import("../../api/services/childProfileService").childProfileService;

let useChildStore: ChildStore;
let childProfileService: ChildProfileService;

const memoryStorage = (() => {
  let values: Record<string, string> = {};
  return {
    clear: () => {
      values = {};
    },
    getItem: (key: string) => values[key] ?? null,
    key: (index: number) => Object.keys(values)[index] ?? null,
    removeItem: (key: string) => {
      delete values[key];
    },
    setItem: (key: string, value: string) => {
      values[key] = value;
    },
    get length() {
      return Object.keys(values).length;
    },
  };
})();

Object.defineProperty(globalThis, "localStorage", {
  value: memoryStorage,
  configurable: true,
});

beforeAll(async () => {
  useChildStore = (await import("../../store/useChildStore")).default;
  childProfileService = (
    await import("../../api/services/childProfileService")
  ).childProfileService;
});

function profile(
  childId: string,
  overrides: Partial<ChildProfile> = {},
): ChildProfile {
  return {
    child_id: childId,
    user_id: "parent-1",
    name: childId,
    age_group: "6-8",
    interests: [],
    avatar: null,
    is_default: false,
    archived_at: null,
    created_at: "2026-05-23T00:00:00Z",
    updated_at: "2026-05-23T00:00:00Z",
    ...overrides,
  };
}

function resetStore() {
  useChildStore.setState({
    currentChild: null,
    childProfiles: [],
    activeChildId: null,
    defaultChildId: "local-default",
    isLoading: false,
    error: null,
  });
}

describe("useChildStore child profile hydration", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
    resetStore();
  });

  it("auto-selects the only active child profile", () => {
    useChildStore.getState().setChildProfiles([
      profile("child-1", { name: "Ari" }),
    ]);

    expect(useChildStore.getState().currentChild?.child_id).toBe("child-1");
    expect(useChildStore.getState().activeChildId).toBe("child-1");
  });

  it("keeps a persisted active child when multiple active profiles load", () => {
    useChildStore.setState({ activeChildId: "child-2" });

    useChildStore.getState().setChildProfiles([
      profile("child-1", { is_default: true }),
      profile("child-2", { name: "Bea" }),
    ]);

    expect(useChildStore.getState().currentChild?.child_id).toBe("child-2");
    expect(useChildStore.getState().defaultChildId).toBe("child-1");
  });

  it("leaves multi-child parent accounts unselected until the parent chooses", () => {
    useChildStore.getState().setChildProfiles([
      profile("child-1", { is_default: true }),
      profile("child-2", { name: "Bea" }),
    ]);

    expect(useChildStore.getState().currentChild).toBeNull();
    expect(useChildStore.getState().activeChildId).toBeNull();
    expect(useChildStore.getState().defaultChildId).toBe("child-1");
  });

  it("falls back to the server default when the persisted active child is gone", () => {
    useChildStore.setState({ activeChildId: "archived-child" });

    useChildStore.getState().setChildProfiles([
      profile("archived-child", { archived_at: "2026-05-23T00:00:00Z" }),
      profile("child-default", { is_default: true }),
      profile("child-other"),
    ]);

    expect(useChildStore.getState().currentChild?.child_id).toBe(
      "child-default",
    );
    expect(useChildStore.getState().activeChildId).toBe("child-default");
  });

  it("loads server profiles through the service", async () => {
    vi.mocked(childProfileService.list).mockResolvedValueOnce({
      items: [profile("child-1")],
    });

    await useChildStore.getState().loadChildProfiles();

    expect(childProfileService.list).toHaveBeenCalledTimes(1);
    expect(useChildStore.getState().childProfiles).toHaveLength(1);
    expect(useChildStore.getState().currentChild?.child_id).toBe("child-1");
  });
});

/* @vitest-environment node */

import { beforeEach, describe, expect, it, vi } from "vitest";

describe("authService Supabase referrals", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
  });

  it("passes referral code through Supabase signUp metadata", async () => {
    vi.stubGlobal("window", {
      location: {
        origin: "http://localhost:5173",
      },
    });

    const signUp = vi.fn().mockResolvedValue({
      data: { session: null },
      error: null,
    });

    vi.doMock("../client", () => ({
      default: {
        post: vi.fn(),
        get: vi.fn(),
      },
    }));

    vi.doMock("@/lib/supabase", () => ({
      default: {
        auth: {
          signUp,
        },
      },
      isSupabaseEnabled: () => true,
    }));

    const { authService } = await import("./authService");

    await authService.register({
      username: "friend",
      email: "friend@test.com",
      password: "password123",
      referral_code: "abc12345",
    });

    expect(signUp).toHaveBeenCalledWith({
      email: "friend@test.com",
      password: "password123",
      options: {
        emailRedirectTo: window.location.origin,
        data: expect.objectContaining({
          username: "friend",
          display_name: "friend",
          role: "parent",
          referral_code: "abc12345",
        }),
      },
    });
  });
});

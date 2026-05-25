/* @vitest-environment node */

import { beforeEach, describe, expect, it, vi } from "vitest";
import apiClient from "../client";
import { authService } from "./authService";

vi.mock("../client", () => ({
  default: {
    post: vi.fn(),
    get: vi.fn(),
  },
}));

vi.mock("@/lib/supabase", () => ({
  default: null,
  isSupabaseEnabled: () => false,
}));

describe("authService registration ownership", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("passes parent-owned child profile fields during legacy registration", async () => {
    const response = {
      user: {
        user_id: "u1",
        username: "parent",
        email: "parent@test.com",
        display_name: "Parent",
        avatar_url: null,
        is_active: true,
        is_verified: false,
        role: "parent",
        created_at: "2026-01-01T00:00:00",
        last_login_at: null,
        membership_tier: "free",
        referral_code: "abc12345",
      },
      token: {
        access_token: "token",
        token_type: "bearer",
        expires_in: 3600,
      },
    };
    vi.mocked(apiClient.post).mockResolvedValueOnce({ data: response });

    await authService.register({
      username: "parent",
      email: "parent@test.com",
      password: "password123",
      role: "parent",
      child_id: "child_alpha",
      child_name: "Ada",
      child_age_group: "6-8",
      child_interests: ["Space"],
    });

    expect(apiClient.post).toHaveBeenCalledWith("/users/register", {
      username: "parent",
      email: "parent@test.com",
      password: "password123",
      role: "parent",
      child_id: "child_alpha",
      child_name: "Ada",
      child_age_group: "6-8",
      child_interests: ["Space"],
    });
  });

  it("passes referral code during legacy registration", async () => {
    const response = {
      user: {
        user_id: "u2",
        username: "friend",
        email: "friend@test.com",
        display_name: "Friend",
        avatar_url: null,
        is_active: true,
        is_verified: false,
        role: "parent",
        created_at: "2026-01-01T00:00:00",
        last_login_at: null,
        membership_tier: "free",
        referral_code: "friend01",
      },
      token: {
        access_token: "token",
        token_type: "bearer",
        expires_in: 3600,
      },
    };
    vi.mocked(apiClient.post).mockResolvedValueOnce({ data: response });

    await authService.register({
      username: "friend",
      email: "friend@test.com",
      password: "password123",
      referral_code: "abc12345",
    });

    expect(apiClient.post).toHaveBeenCalledWith("/users/register", {
      username: "friend",
      email: "friend@test.com",
      password: "password123",
      referral_code: "abc12345",
      role: "parent",
    });
  });

  it("supports parent approval endpoints", async () => {
    vi.mocked(apiClient.post)
      .mockResolvedValueOnce({
        data: {
          status: "pending_parent_consent",
          parent_email: "parent@test.com",
          approval_url: "http://test/parent-approval?token=abc",
        },
      })
      .mockResolvedValueOnce({
        data: {
          status: "approved",
          user_id: "child",
          consent_status: "approved",
        },
      });

    await expect(authService.resendParentApproval()).resolves.toMatchObject({
      status: "pending_parent_consent",
    });
    await expect(authService.approveParentApprovalToken("abc")).resolves.toMatchObject({
      consent_status: "approved",
    });

    expect(apiClient.post).toHaveBeenNthCalledWith(
      1,
      "/users/me/parent-approval/resend",
    );
    expect(apiClient.post).toHaveBeenNthCalledWith(
      2,
      "/users/parent-approval/approve",
      { token: "abc" },
    );
  });
});

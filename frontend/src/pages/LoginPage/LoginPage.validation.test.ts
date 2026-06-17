/* @vitest-environment node */

import { describe, expect, it } from "vitest";

import { isValidRegistrationUsername } from "./validation";

describe("LoginPage registration validation", () => {
  it("accepts backend-compatible usernames", () => {
    expect(isValidRegistrationUsername("parent_1")).toBe(true);
    expect(isValidRegistrationUsername("kid-test")).toBe(true);
  });

  it("rejects email-shaped usernames before submit", () => {
    expect(isValidRegistrationUsername("parent@example.com")).toBe(false);
  });
});

import { describe, expect, it } from "vitest";
import { PUBLIC_NAV_ITEMS } from "./publicNav";

describe("logged-out public navigation", () => {
  it("exposes a single About Us destination", () => {
    expect(PUBLIC_NAV_ITEMS).toEqual([
      {
        href: "/#about-us",
        label: "About Us",
      },
    ]);
  });
});

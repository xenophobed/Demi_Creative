import { describe, expect, it } from "vitest";
import {
  isPictureBookAutoplayAllowed,
  splitStoryIntoPictureBookPages,
} from ".";

describe("splitStoryIntoPictureBookPages", () => {
  it("creates stable picture-book pages from story paragraphs", () => {
    const pages = splitStoryIntoPictureBookPages(
      [
        "Mina opened the glowing door and found a garden of songs.",
        "Every flower hummed a different tune, and her painted dragon listened closely.",
        "Together they chose the kindest melody and carried it home.",
      ].join("\n\n"),
      90,
    );

    expect(pages).toHaveLength(3);
    expect(pages[0]).toEqual({
      id: "page-0",
      text: "Mina opened the glowing door and found a garden of songs.",
    });
  });

  it("splits long paragraphs on sentence boundaries", () => {
    const pages = splitStoryIntoPictureBookPages(
      "First sentence is bright and brave. Second sentence takes the hero over the hill. Third sentence brings everyone safely back.",
      55,
    );

    expect(pages.length).toBeGreaterThan(1);
    expect(pages[0].text.endsWith(".")).toBe(true);
  });

  it("returns no pages for empty story text", () => {
    expect(splitStoryIntoPictureBookPages(" \n\n ")).toEqual([]);
  });
});

describe("isPictureBookAutoplayAllowed", () => {
  it("allows autoplay for multi-page books when motion is OK", () => {
    expect(isPictureBookAutoplayAllowed(false, 2)).toBe(true);
  });

  it("blocks autoplay when the user prefers reduced motion", () => {
    expect(isPictureBookAutoplayAllowed(true, 3)).toBe(false);
  });

  it("blocks autoplay for a single-page book", () => {
    expect(isPictureBookAutoplayAllowed(false, 1)).toBe(false);
  });
});

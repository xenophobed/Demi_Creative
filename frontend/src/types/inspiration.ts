export type InspirationCategory =
  | "art_project" | "invention" | "recycling"
  | "science_craft" | "performance";

export type CtaType = "draw" | "story" | "explore";

export interface AgeAdaptation {
  summary: string;
  creative_prompt: string;
}

export interface InspirationCard {
  id: string;
  title: string;
  summary: string;
  source_hint: string;
  creative_prompt: string;
  category: InspirationCategory;
  illustration_emoji: string;
  cta_type: CtaType;
  cta_route: string;
  age_adaptations: Record<string, AgeAdaptation>;
}

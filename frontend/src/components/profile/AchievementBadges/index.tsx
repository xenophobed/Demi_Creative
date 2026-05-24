import {
  BookOpen,
  GitBranch,
  Image,
  LucideIcon,
  Medal,
  Newspaper,
  Sparkles,
  Volume2,
} from "lucide-react";
import Card from "@/components/common/Card";
import type {
  AchievementDefinition,
  AchievementItem,
  AgeGroup,
} from "@/types/api";

interface AchievementBadgesProps {
  items: AchievementItem[];
  availableDefinitions: AchievementDefinition[];
  ageGroup?: AgeGroup | null;
  isLoading?: boolean;
}

const iconMap: Record<string, LucideIcon> = {
  "book-open": BookOpen,
  "git-branch": GitBranch,
  image: Image,
  newspaper: Newspaper,
  sparkles: Sparkles,
  "volume-2": Volume2,
};

function getAgeCopy(ageGroup?: AgeGroup | null) {
  if (ageGroup === "3-5") {
    return {
      title: "My Badges",
      empty: "New badges will appear after creative play.",
      progress: "creative moments",
    };
  }
  if (ageGroup === "9-12") {
    return {
      title: "Creative Milestones",
      empty: "Milestones will show up as projects are completed.",
      progress: "milestones unlocked",
    };
  }
  return {
    title: "Achievement Badges",
    empty: "Badges will appear as stories, characters, and episodes grow.",
    progress: "badges earned",
  };
}

export default function AchievementBadges({
  items,
  availableDefinitions,
  ageGroup,
  isLoading = false,
}: AchievementBadgesProps) {
  const copy = getAgeCopy(ageGroup);
  const earnedIds = new Set(items.map((item) => item.achievement_id));
  const definitions =
    availableDefinitions.length > 0
      ? availableDefinitions
      : items
          .map((item) => item.definition)
          .filter((definition): definition is AchievementDefinition =>
            Boolean(definition),
          );
  const totalCount = Math.max(definitions.length, items.length);

  return (
    <Card className="p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-bold text-gray-800">{copy.title}</h2>
          <p className="text-sm text-gray-500">
            {isLoading
              ? "Checking saved progress..."
              : `${items.length} of ${totalCount} ${copy.progress}`}
          </p>
        </div>
        <div className="rounded-full bg-amber-50 px-3 py-1 text-sm font-semibold text-amber-700">
          {items.length}
        </div>
      </div>

      {isLoading ? (
        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
          {[0, 1, 2].map((index) => (
            <div
              key={index}
              className="h-24 animate-pulse rounded-lg bg-gray-100"
            />
          ))}
        </div>
      ) : definitions.length === 0 ? (
        <p className="mt-4 rounded-lg border border-dashed border-gray-200 bg-gray-50 px-4 py-5 text-sm text-gray-500">
          {copy.empty}
        </p>
      ) : (
        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
          {definitions.map((definition) => {
            const isEarned = earnedIds.has(definition.achievement_id);
            const Icon = iconMap[definition.icon] ?? Medal;

            return (
              <div
                key={definition.achievement_id}
                className={`min-h-28 rounded-lg border p-3 transition-colors ${
                  isEarned
                    ? "border-amber-200 bg-amber-50"
                    : "border-gray-200 bg-gray-50 opacity-70"
                }`}
              >
                <div
                  className={`mb-3 flex h-10 w-10 items-center justify-center rounded-full ${
                    isEarned
                      ? "bg-amber-100 text-amber-700"
                      : "bg-white text-gray-400"
                  }`}
                >
                  <Icon size={20} aria-hidden="true" />
                </div>
                <h3 className="text-sm font-bold text-gray-800">
                  {definition.title}
                </h3>
                <p className="mt-1 text-xs leading-relaxed text-gray-500">
                  {definition.description}
                </p>
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}

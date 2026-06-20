import {
  Beef,
  Bird,
  Bug,
  Cat,
  Crown,
  Dog,
  Drumstick,
  Feather,
  Fish,
  Flame,
  Leaf,
  LucideIcon,
  Panda,
  PawPrint,
  PiggyBank,
  Rabbit,
  Rat,
  Shell,
  Sparkles,
  Squirrel,
  Turtle,
} from "lucide-react";

import { ANIMAL_EMOJIS } from "@/lib/avatars";

const ANIMAL_ICON_BY_AVATAR_ID: Record<string, LucideIcon> = {
  "emoji:🐶": Dog,
  "emoji:🐱": Cat,
  "emoji:🐼": Panda,
  "emoji:🐨": Leaf,
  "emoji:🦊": Squirrel,
  "emoji:🐰": Rabbit,
  "emoji:🐸": Bug,
  "emoji:🦁": Crown,
  "emoji:🐯": PawPrint,
  "emoji:🐮": Beef,
  "emoji:🐷": PiggyBank,
  "emoji:🐵": Rat,
  "emoji:🐔": Drumstick,
  "emoji:🐧": Bird,
  "emoji:🦄": Sparkles,
  "emoji:🐲": Flame,
  "emoji:🐢": Turtle,
  "emoji:🦋": Feather,
  "emoji:🐬": Fish,
  "emoji:🐙": Shell,
};

const ANIMAL_EMOJI_SET = new Set<string>(ANIMAL_EMOJIS);
const FALLBACK_ANIMAL_ICONS: LucideIcon[] = [
  Dog,
  Cat,
  Rabbit,
  Bird,
  Fish,
  Turtle,
  Squirrel,
  Bug,
  PawPrint,
];

export function normalizeAvatarId(
  avatarId: string | null | undefined,
): string | null {
  if (!avatarId) return null;

  const trimmed = avatarId.trim();
  if (!trimmed) return null;

  if (trimmed.startsWith("emoji:")) return trimmed;
  if (ANIMAL_EMOJI_SET.has(trimmed)) return `emoji:${trimmed}`;

  return trimmed;
}

function fallbackIconForId(avatarId: string): LucideIcon {
  let hash = 0;
  for (const char of avatarId) {
    hash = (hash * 31 + char.codePointAt(0)!) % FALLBACK_ANIMAL_ICONS.length;
  }

  return FALLBACK_ANIMAL_ICONS[hash];
}

export function avatarIconForId(avatarId: string | null | undefined): LucideIcon {
  const normalized = normalizeAvatarId(avatarId);
  if (!normalized) return PawPrint;

  return ANIMAL_ICON_BY_AVATAR_ID[normalized] ?? fallbackIconForId(normalized);
}

export function isAnimalAvatarId(
  avatarId: string | null | undefined,
): boolean {
  const normalized = normalizeAvatarId(avatarId);
  return Boolean(normalized && ANIMAL_ICON_BY_AVATAR_ID[normalized]);
}

export function AnimalAvatarIcon({
  avatarId,
  size = 22,
  className,
}: {
  avatarId: string | null | undefined;
  size?: number;
  className?: string;
}) {
  const Icon = avatarIconForId(avatarId);
  return <Icon size={size} className={className} aria-hidden="true" />;
}

/**
 * AgentTitlePicker — dropdown of curated buddy titles + optional free-text
 * input for older children (PRD §3.11.2).
 *
 * Issue: #442 | Parent epic: #436
 */

import { useState } from "react";
import { CURATED_TITLES, customTitleAllowed } from "@/lib/agentTitles";
import type { AgeGroup } from "@/types/api";

const CUSTOM_SENTINEL = "__custom__";

interface Props {
  value: string;
  onChange: (next: string) => void;
  ageGroup: AgeGroup | undefined | null;
  disabled?: boolean;
  error?: string | null;
}

export default function AgentTitlePicker({
  value,
  onChange,
  ageGroup,
  disabled,
  error,
}: Props) {
  const allowCustom = customTitleAllowed(ageGroup);
  const isCurated = (CURATED_TITLES as readonly string[]).includes(value);
  // When the current value is not in the curated list, we must be in
  // custom mode (or the parent is restoring server state). For ages
  // <9-12 this can happen if someone tampers with the field — we
  // surface the value in a read-only fallback.
  const [mode, setMode] = useState<"curated" | "custom">(
    isCurated || !value ? "curated" : "custom",
  );

  const onSelectChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const v = e.target.value;
    if (v === CUSTOM_SENTINEL) {
      setMode("custom");
      onChange("");
      return;
    }
    setMode("curated");
    onChange(v);
  };

  const onCustomChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onChange(e.target.value.slice(0, 32));
  };

  const selectValue = mode === "custom" ? CUSTOM_SENTINEL : value;

  return (
    <div className="flex flex-col gap-2">
      <label className="text-sm font-medium text-gray-700">
        Buddy title
      </label>
      <select
        className="w-full rounded-md border border-gray-300 px-3 py-2 focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500 disabled:bg-gray-100"
        value={selectValue}
        disabled={disabled}
        onChange={onSelectChange}
        aria-label="Buddy title"
      >
        <option value="" disabled>
          Pick a title…
        </option>
        {CURATED_TITLES.map((title) => (
          <option key={title} value={title}>
            {title}
          </option>
        ))}
        {allowCustom && (
          <option value={CUSTOM_SENTINEL}>✏️ Custom title</option>
        )}
      </select>
      {mode === "custom" && allowCustom && (
        <input
          className="w-full rounded-md border border-gray-300 px-3 py-2 focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500 disabled:bg-gray-100"
          type="text"
          value={value}
          maxLength={32}
          placeholder="Type a custom title (1-32 chars)"
          disabled={disabled}
          onChange={onCustomChange}
          aria-label="Custom buddy title"
        />
      )}
      {error && <p className="text-xs text-red-600">{error}</p>}
    </div>
  );
}

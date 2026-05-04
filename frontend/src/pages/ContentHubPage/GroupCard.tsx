/**
 * GroupCard — single group entry on the ContentHubPage directory.
 *
 * Issue: #451 | Parent epic: #437
 */

import type { Group } from "@/types/hub";

interface Props {
  group: Group;
  onOpen: () => void;
  onJoin?: () => void;
  joined: boolean;
}

export default function GroupCard({ group, onOpen, onJoin, joined }: Props) {
  const isPrivate = group.visibility === "private";
  return (
    <article
      className="group flex flex-col gap-2 rounded-2xl border border-gray-200 bg-white p-5 shadow-sm transition-all hover:shadow-md"
    >
      <header className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <h3 className="text-lg font-semibold text-gray-900 line-clamp-1">
            {group.name}
          </h3>
          <p className="text-xs text-gray-500">
            {group.member_count}{" "}
            {group.member_count === 1 ? "member" : "members"} ·{" "}
            {isPrivate ? "Private" : "Public"}
          </p>
        </div>
        <span
          className={[
            "rounded-full px-2 py-0.5 text-xs font-semibold",
            isPrivate
              ? "bg-amber-100 text-amber-700"
              : "bg-emerald-100 text-emerald-700",
          ].join(" ")}
        >
          {isPrivate ? "🔒 Private" : "🌐 Public"}
        </span>
      </header>

      {group.description && (
        <p className="text-sm text-gray-600 line-clamp-2">{group.description}</p>
      )}

      <footer className="mt-2 flex items-center gap-2">
        <button
          type="button"
          className="rounded-md bg-violet-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-violet-700"
          onClick={onOpen}
        >
          Open
        </button>
        {onJoin && !joined && (
          <button
            type="button"
            className="rounded-md border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
            onClick={onJoin}
          >
            {isPrivate ? "Join with invite" : "Join"}
          </button>
        )}
        {joined && (
          <span className="text-xs font-medium text-emerald-600">
            ✓ Joined
          </span>
        )}
      </footer>
    </article>
  );
}

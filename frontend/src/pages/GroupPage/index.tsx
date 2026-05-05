/**
 * GroupPage — magazine-spread per-group feed (Option A redesign).
 *
 * Layout:
 *   - Hero banner with deterministic theme gradient, theme emoji, group
 *     name in display font, member + visibility chips, and an italic
 *     description line
 *   - 1/2/3-column responsive grid of magazine-style PostCards
 *   - Animated empty state with the shared rainbow + balloon set
 *   - Cursor-paginated load-more button
 *
 * Issue: GroupPage magazine redesign | Parent epic: #437
 */

import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { AxiosError } from "axios";
import { motion } from "framer-motion";
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { hubService } from "@/api/services/hubService";
import type {
  Group,
  HubPost,
  HubPostCursor,
  ListHubPostsResponse,
} from "@/types/hub";
import PostCard from "./PostCard";
import { accentForSlug, emojiForTheme } from "./groupTheme";

const PAGE_SIZE = 10;

function isAxios403(err: unknown): boolean {
  return err instanceof AxiosError && err.response?.status === 403;
}

export default function GroupPage() {
  const { slug } = useParams<{ slug: string }>();
  const navigate = useNavigate();
  const [forbidden, setForbidden] = useState(false);
  const accent = accentForSlug(slug);

  const { data: group, isLoading: groupLoading } = useQuery<Group | null>({
    queryKey: ["hub-group", slug],
    queryFn: () => hubService.getGroup(slug as string),
    enabled: Boolean(slug),
  });

  const themeEmoji = emojiForTheme(group?.theme ?? group?.name);

  const {
    data,
    fetchNextPage,
    hasNextPage,
    isLoading: postsLoading,
    isFetchingNextPage,
    error,
  } = useInfiniteQuery<ListHubPostsResponse, unknown>({
    queryKey: ["hub-group-posts", group?.group_id],
    enabled: Boolean(group?.group_id),
    initialPageParam: undefined as HubPostCursor | undefined,
    queryFn: async ({ pageParam }) =>
      hubService.listGroupPosts(group!.group_id, {
        limit: PAGE_SIZE,
        cursor: (pageParam as HubPostCursor | undefined) ?? null,
      }),
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  });

  useEffect(() => {
    if (isAxios403(error)) setForbidden(true);
  }, [error]);

  if (groupLoading) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-8 text-gray-500">
        Loading group…
      </div>
    );
  }

  if (!group) {
    return (
      <div className="mx-auto flex max-w-3xl flex-col gap-3 px-4 py-12 text-center">
        <span className="text-5xl">🔭</span>
        <p className="text-lg font-medium text-gray-700">
          Couldn't find that group.
        </p>
        <Link
          to="/content-hub"
          className="text-sm font-medium text-violet-700 underline"
        >
          Back to Content Hub
        </Link>
      </div>
    );
  }

  if (forbidden) {
    return (
      <div className="mx-auto flex max-w-4xl flex-col gap-6 px-4 py-8">
        <div
          className={`overflow-hidden rounded-3xl bg-gradient-to-br ${accent.bannerGradient} px-8 py-10 shadow-sm`}
        >
          <h1 className="text-3xl font-bold text-gray-900">{group.name}</h1>
          <p className="mt-2 text-sm text-gray-700">Private group</p>
        </div>
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-6">
          <p className="text-base font-medium text-amber-900">
            🔒 This is a private group.
          </p>
          <p className="mt-1 text-sm text-amber-800">
            Open the invite link a friend sent you to join, then come back to
            see what they're sharing.
          </p>
          <Link
            to="/content-hub"
            className="mt-3 inline-block text-sm font-semibold text-violet-700 underline"
          >
            Back to Content Hub
          </Link>
        </div>
      </div>
    );
  }

  const posts: HubPost[] = (data?.pages ?? []).flatMap((p) => p.items);
  const memberLabel =
    group.member_count === 1 ? "1 member" : `${group.member_count} members`;

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-8">
      {/* Hero banner */}
      <header
        className={`relative overflow-hidden rounded-3xl bg-gradient-to-br ${accent.bannerGradient} px-6 py-8 shadow-sm sm:px-10 sm:py-12`}
      >
        {/* Decorative floating emoji on the right */}
        <motion.span
          aria-hidden="true"
          className="pointer-events-none absolute right-4 top-4 text-7xl opacity-90 sm:right-10 sm:top-6 sm:text-8xl"
          animate={{ y: [0, -6, 0] }}
          transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
        >
          {themeEmoji}
        </motion.span>

        <div className="relative flex flex-col gap-2">
          <Link
            to="/content-hub"
            className={`text-xs font-semibold uppercase tracking-wider ${accent.accentText} hover:underline`}
          >
            ← Content Hub
          </Link>
          <h1 className="text-3xl font-bold text-gray-900 sm:text-4xl">
            {group.name}
          </h1>
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span
              className={`rounded-full px-2.5 py-0.5 font-semibold ${accent.chipBg}`}
            >
              {group.visibility === "private" ? "🔒 Private" : "🌐 Public"}
            </span>
            <span className="rounded-full bg-white/70 px-2.5 py-0.5 font-medium text-gray-700">
              {memberLabel}
            </span>
            {group.theme && (
              <span
                className={`rounded-full px-2.5 py-0.5 font-medium ${accent.chipBg}`}
              >
                #{group.theme}
              </span>
            )}
          </div>
          {group.description && (
            <p className="mt-2 max-w-2xl text-sm italic text-gray-700">
              {group.description}
            </p>
          )}
        </div>
      </header>

      {/* Posts */}
      {postsLoading && <p className="text-gray-500">Loading stories…</p>}

      {!postsLoading && posts.length === 0 && (
        <div className="flex flex-col items-center gap-4 rounded-3xl border-2 border-dashed border-gray-200 bg-white px-6 py-12 text-center shadow-sm">
          <div className="flex justify-center gap-3 text-5xl">
            <motion.span
              animate={{ y: [0, -8, 0] }}
              transition={{ duration: 2.4, repeat: Infinity, delay: 0 }}
            >
              🌟
            </motion.span>
            <motion.span
              animate={{ y: [0, -8, 0] }}
              transition={{ duration: 2.4, repeat: Infinity, delay: 0.4 }}
            >
              🎈
            </motion.span>
            <motion.span
              animate={{ y: [0, -8, 0] }}
              transition={{ duration: 2.4, repeat: Infinity, delay: 0.8 }}
            >
              🌈
            </motion.span>
          </div>
          <div>
            <p className="text-lg font-semibold text-gray-800">
              The first story here gets the spotlight!
            </p>
            <p className="mt-1 text-sm text-gray-600">
              Make a story and tap "Share to Content Hub" to drop it in.
            </p>
          </div>
          <button
            type="button"
            className="rounded-full bg-violet-600 px-5 py-2 text-sm font-semibold text-white shadow-sm hover:bg-violet-700"
            onClick={() => navigate("/upload")}
          >
            Make a story
          </button>
        </div>
      )}

      {posts.length > 0 && (
        <section className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-3">
          {posts.map((p) => (
            <PostCard key={p.post_id} post={p} />
          ))}
        </section>
      )}

      {hasNextPage && (
        <div className="flex justify-center">
          <button
            type="button"
            className="rounded-full border border-gray-300 bg-white px-5 py-2 text-sm font-semibold text-gray-700 shadow-sm hover:bg-gray-50 disabled:opacity-50"
            onClick={() => fetchNextPage()}
            disabled={isFetchingNextPage}
          >
            {isFetchingNextPage ? "Loading…" : "Load more stories"}
          </button>
        </div>
      )}
    </div>
  );
}

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
import { ArrowLeft, Lock, Sparkles, Users } from "lucide-react";
import { hubService } from "@/api/services/hubService";
import type {
  Group,
  HubPost,
  HubPostCursor,
  ListHubPostsResponse,
} from "@/types/hub";
import PostCard from "./PostCard";
import { emojiForTheme } from "./groupTheme";

const PAGE_SIZE = 10;

function isAxios403(err: unknown): boolean {
  return err instanceof AxiosError && err.response?.status === 403;
}

export default function GroupPage() {
  const { slug } = useParams<{ slug: string }>();
  const navigate = useNavigate();
  const [forbidden, setForbidden] = useState(false);

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
      <div className="k12-page-narrow text-gray-500">
        Loading group…
      </div>
    );
  }

  if (!group) {
    return (
      <div className="k12-page-narrow items-center py-12 text-center">
        <span className="text-5xl">🔭</span>
        <p className="text-lg font-medium text-gray-700">
          Couldn't find that group.
        </p>
        <Link
          to="/content-hub"
          className="text-sm font-medium text-primary-dark underline"
        >
          Back to Content Hub
        </Link>
      </div>
    );
  }

  if (forbidden) {
    return (
      <div className="k12-page-narrow">
        <div className="k12-hero">
          <h1 className="k12-hero-title">{group.name}</h1>
          <p className="mt-2 text-sm text-gray-700">Private group</p>
        </div>
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-6">
          <p className="flex items-center gap-2 text-base font-bold text-amber-900">
            <Lock size={18} /> This is a private group.
          </p>
          <p className="mt-1 text-sm text-amber-800">
            Open the invite link a friend sent you to join, then come back to
            see what they're sharing.
          </p>
          <Link
            to="/content-hub"
            className="mt-3 inline-block text-sm font-semibold text-primary-dark underline"
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
    <div className="k12-page">
      {/* Hero banner */}
      <header className="k12-hero relative overflow-hidden">
        {/* Decorative floating emoji on the right */}
        <motion.span
          aria-hidden="true"
          className="pointer-events-none absolute right-5 top-5 text-6xl opacity-80 sm:right-8 sm:text-7xl"
          animate={{ y: [0, -6, 0] }}
          transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
        >
          {themeEmoji}
        </motion.span>

        <div className="relative flex flex-col gap-2">
          <Link
            to="/content-hub"
            className="inline-flex w-fit items-center gap-1 text-xs font-bold uppercase tracking-wide text-primary-dark hover:underline"
          >
            <ArrowLeft size={14} /> Content Hub
          </Link>
          <h1 className="k12-hero-title">
            {group.name}
          </h1>
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span
              className={group.visibility === "private" ? "k12-chip bg-accent/45 text-yellow-800" : "k12-chip bg-secondary/15 text-teal-700"}
            >
              {group.visibility === "private" ? <Lock size={12} /> : <Users size={12} />}
              {group.visibility === "private" ? "Private" : "Public"}
            </span>
            <span className="k12-chip bg-white/75 text-gray-700">
              <Users size={12} />
              {memberLabel}
            </span>
            {group.theme && (
              <span
                className="k12-chip bg-primary/10 text-primary-dark"
              >
                #{group.theme}
              </span>
            )}
          </div>
          {group.description && (
            <p className="k12-hero-copy">
              {group.description}
            </p>
          )}
        </div>
      </header>

      {/* Posts */}
      {postsLoading && <p className="text-gray-500">Loading stories…</p>}

      {!postsLoading && posts.length === 0 && (
        <div className="k12-panel flex flex-col items-center gap-4 border-2 border-dashed border-gray-200 px-6 py-12 text-center">
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
            className="k12-button-primary"
            onClick={() => navigate("/upload")}
          >
            <Sparkles size={16} />
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
            className="k12-button-secondary"
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

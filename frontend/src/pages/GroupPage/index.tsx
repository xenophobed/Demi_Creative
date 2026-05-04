/**
 * GroupPage — per-group feed at /content-hub/:slug.
 *
 * Resolves the slug to a group id, then paginates through hub_posts
 * via the cursor returned by listGroupPosts. Renders an empty state
 * with a "Be the first to share!" CTA pointing at /upload (or the
 * relevant creation flow) when the group has no posts.
 *
 * Visibility:
 *   - Public groups: any authenticated user can read.
 *   - Private groups: members only — the backend returns 403 NOT_A_MEMBER
 *     and we surface a join CTA pointing at the invite-link flow.
 *
 * Issue: #452 | Parent epic: #437
 */

import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { AxiosError } from "axios";
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { hubService } from "@/api/services/hubService";
import type {
  Group,
  HubPost,
  HubPostCursor,
  ListHubPostsResponse,
} from "@/types/hub";
import PostCard from "./PostCard";

const PAGE_SIZE = 10;

function isAxios403(err: unknown): boolean {
  return err instanceof AxiosError && err.response?.status === 403;
}

export default function GroupPage() {
  const { slug } = useParams<{ slug: string }>();
  const navigate = useNavigate();
  const [forbidden, setForbidden] = useState(false);

  // Resolve slug -> group_id (the post-feed endpoint uses ids).
  const { data: group, isLoading: groupLoading } = useQuery<Group | null>({
    queryKey: ["hub-group", slug],
    queryFn: () => hubService.getGroup(slug as string),
    enabled: Boolean(slug),
  });

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

  if (groupLoading || (!group && !groupLoading)) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-8 text-gray-500">
        {groupLoading ? "Loading group…" : "Group not found."}
      </div>
    );
  }

  const posts: HubPost[] = (data?.pages ?? []).flatMap((p) => p.items);

  if (forbidden) {
    return (
      <div className="mx-auto flex max-w-3xl flex-col gap-4 px-4 py-8">
        <h1 className="text-2xl font-semibold text-gray-900">{group!.name}</h1>
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-6">
          <p className="text-base font-medium text-amber-900">
            This is a private group.
          </p>
          <p className="mt-1 text-sm text-amber-800">
            Open the invite link a friend sent you to join, then come back to
            see what they're sharing.
          </p>
          <Link
            to="/content-hub"
            className="mt-3 inline-block text-sm font-medium text-violet-700 underline"
          >
            Back to Content Hub
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-8">
      <header className="flex flex-col gap-1">
        <p className="text-xs font-medium uppercase tracking-wide text-violet-600">
          Content Hub
        </p>
        <h1 className="text-2xl font-semibold text-gray-900">{group!.name}</h1>
        <p className="text-sm text-gray-600">
          {group!.member_count}{" "}
          {group!.member_count === 1 ? "member" : "members"} ·{" "}
          {group!.visibility === "private" ? "Private" : "Public"}
          {group!.theme ? ` · ${group!.theme}` : ""}
        </p>
        {group!.description && (
          <p className="mt-1 text-sm text-gray-700">{group!.description}</p>
        )}
      </header>

      {postsLoading && <p className="text-gray-500">Loading posts…</p>}

      {!postsLoading && posts.length === 0 && (
        <div className="rounded-2xl border-2 border-dashed border-gray-200 bg-white p-8 text-center">
          <p className="text-base font-medium text-gray-700">
            Be the first to share!
          </p>
          <p className="mt-1 text-sm text-gray-500">
            Make a story and tap "Share to Content Hub" to drop it here.
          </p>
          <button
            type="button"
            className="mt-4 rounded-md bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-700"
            onClick={() => navigate("/upload")}
          >
            Make a story
          </button>
        </div>
      )}

      {posts.length > 0 && (
        <section className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {posts.map((p) => (
            <PostCard key={p.post_id} post={p} />
          ))}
        </section>
      )}

      {hasNextPage && (
        <div className="flex justify-center">
          <button
            type="button"
            className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
            onClick={() => fetchNextPage()}
            disabled={isFetchingNextPage}
          >
            {isFetchingNextPage ? "Loading…" : "Load more"}
          </button>
        </div>
      )}
    </div>
  );
}

/**
 * SignInPrompt — shared empty-state for pages that need an auth session.
 * Used by /my-agent and /content-hub guest views so the experience is
 * aligned across the app.
 *
 * Issue: ui-polish on top of #442 / #444 / #451
 */

import { Link } from "react-router-dom";

interface Props {
  icon?: string;
  title: string;
  description: string;
  /** Where to come back to after sign-in. Optional — defaults to current path. */
  returnPath?: string;
}

export default function SignInPrompt({
  icon = "👋",
  title,
  description,
  returnPath,
}: Props) {
  const ret =
    returnPath ?? (typeof window !== "undefined" ? window.location.pathname : "/");
  const href = `/login?return=${encodeURIComponent(ret)}`;
  return (
    <div className="mx-auto flex max-w-2xl flex-col items-center gap-3 rounded-lg border-2 border-dashed border-primary/20 bg-white px-6 py-10 text-center">
      <span className="text-4xl" aria-hidden="true">
        {icon}
      </span>
      <h2 className="text-xl font-semibold text-gray-900">{title}</h2>
      <p className="max-w-md text-sm text-gray-600">{description}</p>
      <Link
        to={href}
        className="k12-button-primary mt-2"
      >
        Sign in
      </Link>
    </div>
  );
}

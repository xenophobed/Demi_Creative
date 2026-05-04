/**
 * AgentBylineChip — small "By <buddy>" tile reused across surfaces (#445).
 *
 * Renders nothing when the agent prop is missing so callers don't have
 * to gate the render. Avatar uses the existing AvatarDisplay component
 * which already understands the "emoji:<emoji>" prefix used by the
 * shared avatar whitelist.
 *
 * Issue: #445 | Parent epic: #436
 */

import AvatarDisplay from "@/components/common/AvatarDisplay";
import type { Agent } from "@/types/agent";

interface Props {
  agent: Agent | null | undefined;
  className?: string;
}

export default function AgentBylineChip({ agent, className = "" }: Props) {
  if (!agent) return null;
  const text = `By ${agent.agent_name} the ${agent.agent_title}`;
  return (
    <div
      className={`inline-flex items-center gap-1.5 text-xs text-gray-500 ${className}`}
      title={text}
    >
      <AvatarDisplay avatarUrl={agent.agent_avatar_id} size="sm" />
      <span className="truncate">
        By <span className="font-semibold text-gray-700">{agent.agent_name}</span>{" "}
        the {agent.agent_title}
      </span>
    </div>
  );
}

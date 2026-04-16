import type { AgentResponse, ChatThreadResponse } from '../api/generated'

export type AgentWithThreads = AgentResponse & {
  threads: ChatThreadResponse[]
}

function getThreadTimestamp(thread: ChatThreadResponse): number {
  const value = thread.last_message_at ?? thread.updated_at ?? thread.created_at
  return new Date(value).getTime()
}

export function groupThreadsByAgent(
  agents: AgentResponse[],
  threads: ChatThreadResponse[],
): AgentWithThreads[] {
  const threadMap = new Map<string, ChatThreadResponse[]>()

  for (const thread of threads) {
    const list = threadMap.get(thread.agent_id) ?? []
    list.push(thread)
    threadMap.set(thread.agent_id, list)
  }

  return agents.map((agent) => ({
    ...agent,
    threads: (threadMap.get(agent.id) ?? [])
      .slice()
      .sort((left, right) => getThreadTimestamp(right) - getThreadTimestamp(left)),
  }))
}

export function findAgentById(
  agents: AgentResponse[],
  agentId: string | null,
): AgentResponse | null {
  if (!agentId) {
    return null
  }

  return agents.find((agent) => agent.id === agentId) ?? null
}

export function findThreadById(
  threads: ChatThreadResponse[],
  threadId: string | null,
): ChatThreadResponse | null {
  if (!threadId) {
    return null
  }

  return threads.find((thread) => thread.id === threadId) ?? null
}

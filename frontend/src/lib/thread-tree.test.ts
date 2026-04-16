import { describe, expect, it } from 'vitest'
import type { AgentResponse, ChatThreadResponse } from '../api/generated'
import { groupThreadsByAgent } from './thread-tree'

function createAgent(overrides: Partial<AgentResponse> = {}): AgentResponse {
  return {
    id: 'agent-1',
    name: 'Atlas',
    hermes_home_path: '/tmp/hermes/atlas',
    workspace_key: 'workspace-atlas',
    ...overrides,
  }
}

function createThread(overrides: Partial<ChatThreadResponse> = {}): ChatThreadResponse {
  return {
    id: 'thread-older',
    agent_id: 'agent-1',
    user_id: 'user-1',
    title: 'Older thread',
    hermes_session_id: 'session-1',
    updated_at: '2026-04-16T10:00:00.000Z',
    created_at: '2026-04-16T09:00:00.000Z',
    last_message_at: '2026-04-16T10:00:00.000Z',
    ...overrides,
  }
}

describe('groupThreadsByAgent', () => {
  it('nests threads under their respective agents and sorts newest first', () => {
    const agents: AgentResponse[] = [
      createAgent({ id: 'agent-1', name: 'Atlas' }),
      createAgent({
        id: 'agent-2',
        name: 'Hermes',
        hermes_home_path: '/tmp/hermes/hermes',
        workspace_key: 'workspace-hermes',
      }),
    ]
    const threads: ChatThreadResponse[] = [
      createThread(),
      createThread({
        id: 'thread-newer',
        title: 'Newer thread',
        updated_at: '2026-04-16T12:00:00.000Z',
        created_at: '2026-04-16T11:00:00.000Z',
        last_message_at: '2026-04-16T12:00:00.000Z',
      }),
    ]

    const grouped = groupThreadsByAgent(agents, threads)

    expect(grouped).toHaveLength(2)
    expect(grouped[0].threads.map((thread) => thread.id)).toEqual([
      'thread-newer',
      'thread-older',
    ])
    expect(grouped[1].threads).toEqual([])
  })
})

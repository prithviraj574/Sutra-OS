import { env } from '../lib/env'

export type MessageContent =
  | string
  | Array<{ type: 'text'; text: string } | { type: 'image'; data: string; mime_type: string }>

export type AgentMessage = {
  role: 'user' | 'assistant' | 'toolResult'
  content?: MessageContent | Array<Record<string, unknown>>
  timestamp?: number
  stop_reason?: string
  error_message?: string | null
}

export type AgentSummary = {
  id: string
  user_id: string
  name: string
  created_at: string
  updated_at: string
}

export type SessionSummary = {
  id: string
  user_id: string
  agent_id: string
  status: string
  created_at: string
  updated_at: string
}

export type SessionCreated = {
  session_id: string
  agent_id: string
  user_id: string
}

export type MessagesResponse = {
  session_id: string
  messages: AgentMessage[]
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${env.apiBaseUrl}${path}`, {
    ...init,
    headers: {
      'content-type': 'application/json',
      ...init?.headers,
    },
  })

  if (!response.ok) {
    const body = await response.json().catch(() => undefined)
    throw new Error(getApiErrorMessage(body) || `Request failed: ${response.status}`)
  }

  return response.json() as Promise<T>
}

export function listAgents(userId: string): Promise<AgentSummary[]> {
  const search = new URLSearchParams({ user_id: userId })
  return request(`/v1/agent/agents?${search.toString()}`)
}

export function createAgent(userId: string, name = 'Default agent'): Promise<AgentSummary> {
  return request('/v1/agent/agents', {
    method: 'POST',
    body: JSON.stringify({ user_id: userId, name }),
  })
}

export function listSessions(userId: string, agentId: string): Promise<SessionSummary[]> {
  const search = new URLSearchParams({ user_id: userId })
  return request(`/v1/agent/agents/${agentId}/sessions?${search.toString()}`)
}

export function createSession(
  userId: string,
  agentId: string,
  options: { system_prompt?: string; model?: Record<string, unknown> } = {},
): Promise<SessionCreated> {
  return request(`/v1/agent/agents/${agentId}/sessions`, {
    method: 'POST',
    body: JSON.stringify({ user_id: userId, ...options }),
  })
}

export function listMessages(userId: string, sessionId: string): Promise<MessagesResponse> {
  const search = new URLSearchParams({ user_id: userId })
  return request(`/v1/agent/sessions/${sessionId}/messages?${search.toString()}`)
}

export function sendMessage(
  sessionId: string,
  userId: string,
  content: string,
): Promise<MessagesResponse> {
  return request(`/v1/agent/sessions/${sessionId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ user_id: userId, content, stream: false }),
  })
}

export function getApiErrorMessage(error: unknown): string {
  if (typeof error === 'string' && error.trim()) {
    return error
  }

  if (error && typeof error === 'object' && 'detail' in error) {
    const detail = (error as { detail?: unknown }).detail
    if (typeof detail === 'string' && detail.trim()) {
      return detail
    }
  }

  if (error instanceof Error) {
    return error.message
  }

  return 'Unexpected request failure'
}

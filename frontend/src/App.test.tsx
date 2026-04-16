import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type {
  AgentResponse,
  ChatMessageResponse,
  ChatThreadResponse,
  MeResponse,
  UserResponse,
} from './api/generated'
import App from './App'

const firebaseMocks = vi.hoisted(() => ({
  signInWithGoogle: vi.fn<() => Promise<string>>(),
  signOutFromGoogle: vi.fn<() => Promise<void>>(),
}))

vi.mock('./lib/firebase', () => ({
  signInWithGoogle: firebaseMocks.signInWithGoogle,
  signOutFromGoogle: firebaseMocks.signOutFromGoogle,
}))

type FetchResponsePayload =
  | Record<string, unknown>
  | Array<Record<string, unknown>>
  | string
  | null

type MockRequest = {
  url: string
  method: string
  headers: Headers
}

function toMockRequest(input: RequestInfo | URL, init?: RequestInit): MockRequest {
  if (input instanceof Request) {
    return {
      url: input.url,
      method: input.method,
      headers: input.headers,
    }
  }

  return {
    url: String(input),
    method: init?.method ?? 'GET',
    headers: new Headers(init?.headers),
  }
}

function readHeader(headers: RequestInit['headers'], name: string): string | null {
  if (headers instanceof Headers) {
    return headers.get(name)
  }

  if (Array.isArray(headers)) {
    const match = headers.find(([key]) => key.toLowerCase() === name.toLowerCase())
    return match?.[1] ?? null
  }

  if (!headers) {
    return null
  }

  const key = Object.keys(headers).find((headerName) => headerName.toLowerCase() === name.toLowerCase())
  return key ? String(headers[key as keyof typeof headers]) : null
}

function jsonResponse(payload: FetchResponsePayload): Promise<Response> {
  const textPayload =
    typeof payload === 'string' ? payload : JSON.stringify(payload)

  return Promise.resolve({
    ok: true,
    headers: new Headers({ 'Content-Type': 'application/json' }),
    json: async () => payload,
    text: async () => textPayload,
  } as Response)
}

function createUser(overrides: Partial<UserResponse> = {}): UserResponse {
  return {
    id: 'user-1',
    email: 'ada@example.com',
    name: 'Ada',
    ...overrides,
  }
}

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
    id: 'thread-1',
    agent_id: 'agent-1',
    user_id: 'user-1',
    title: 'Launch Plan',
    hermes_session_id: 'session-1',
    last_message_at: '2026-04-17T07:30:00.000Z',
    updated_at: '2026-04-17T07:30:00.000Z',
    created_at: '2026-04-17T07:00:00.000Z',
    ...overrides,
  }
}

function createMePayload(): MeResponse {
  return {
    user: createUser(),
    agents: [createAgent()],
  }
}

function createMessageResponse(overrides: Partial<ChatMessageResponse> = {}): ChatMessageResponse {
  return {
    thread_id: 'thread-2',
    session_id: 'session-2',
    response_text: 'Here is the first reply.',
    raw_result: {},
    ...overrides,
  }
}

describe('App', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.localStorage.clear()
    vi.stubGlobal('fetch', vi.fn())
  })

  it('renders Google login when there is no active session', () => {
    render(<App />)

    expect(
      screen.getByRole('button', { name: 'Login with Google' }),
    ).toBeInTheDocument()
  })

  it('logs in, exchanges auth, and renders agents with nested threads', async () => {
    const fetchMock = vi.mocked(fetch)
    firebaseMocks.signInWithGoogle.mockResolvedValue('google-id-token')

    fetchMock.mockImplementation((input, init) => {
      const request = toMockRequest(input, init)
      const url = request.url

      if (url === 'http://localhost:8000/auth/exchange') {
        expect(request.method).toBe('POST')
        return jsonResponse({
          access_token: 'talaria-access-token',
          expires_in: 3600,
          user: createUser(),
          agents: [
            createAgent({ id: 'agent-1', name: 'Atlas' }),
            createAgent({
              id: 'agent-2',
              name: 'Hermes',
              hermes_home_path: '/tmp/hermes/hermes',
              workspace_key: 'workspace-hermes',
            }),
          ],
        })
      }

      if (url === 'http://localhost:8000/threads') {
        return jsonResponse([createThread()])
      }

      throw new Error(`Unexpected fetch call: ${url}`)
    })

    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: 'Login with Google' }))

    expect(await screen.findByText('Atlas')).toBeInTheDocument()
    expect(screen.getByText('Hermes')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Launch Plan' })).toBeInTheDocument()
  })

  it('hydrates an existing session and sends a message through new thread flow', async () => {
    const fetchMock = vi.mocked(fetch)

    window.localStorage.setItem(
      'talaria.session',
      JSON.stringify({ accessToken: 'saved-token' }),
    )

    fetchMock.mockImplementation((input, init) => {
      const request = toMockRequest(input, init)
      const url = request.url

      if (url === 'http://localhost:8000/me') {
        expect(readHeader(request.headers, 'authorization')).toBe('Bearer saved-token')
        return jsonResponse(createMePayload())
      }

      if (url === 'http://localhost:8000/threads' && request.method === 'GET') {
        return jsonResponse([])
      }

      if (url === 'http://localhost:8000/threads' && request.method === 'POST') {
        return jsonResponse(
          createThread({
            id: 'thread-2',
            title: 'New Chat',
            hermes_session_id: 'session-2',
            last_message_at: null,
            updated_at: '2026-04-17T08:00:00.000Z',
            created_at: '2026-04-17T08:00:00.000Z',
          }),
        )
      }

      if (url === 'http://localhost:8000/threads/thread-2/messages') {
        expect(request.method).toBe('POST')
        return jsonResponse(createMessageResponse())
      }

      throw new Error(`Unexpected fetch call: ${url}`)
    })

    render(<App />)

    expect(await screen.findByText('No threads yet')).toBeInTheDocument()

    fireEvent.change(screen.getByPlaceholderText('Message your selected agent...'), {
      target: { value: 'Plan the week' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    await waitFor(() => {
      expect(screen.getAllByText('Plan the week').length).toBeGreaterThan(0)
      expect(screen.getByText('Here is the first reply.')).toBeInTheDocument()
    })

    const messageRequest = fetchMock.mock.calls
      .map(([input, init]) => toMockRequest(input, init))
      .find((request) => request.url === 'http://localhost:8000/threads/thread-2/messages')

    expect(messageRequest?.method).toBe('POST')
  })
})

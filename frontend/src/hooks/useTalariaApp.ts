import { startTransition, useEffect, useMemo, useState } from 'react'
import {
  createThreadThreadsPost,
  exchangeAuthTokenAuthExchangePost,
  getMeMeGet,
  listThreadsThreadsGet,
  sendMessageThreadsThreadIdMessagesPost,
} from '../api/generated'
import {
  authorizationHeaders,
  getApiErrorMessage,
  unwrapData,
} from '../api/client'
import { signInWithGoogle, signOutFromGoogle } from '../lib/firebase'
import { clearSession, loadSession, saveSession } from '../lib/session'
import { findAgentById, findThreadById, groupThreadsByAgent } from '../lib/thread-tree'
import type {
  AgentResponse,
  ChatThreadResponse,
  MeResponse,
  UserResponse,
} from '../api/generated'
import type { AgentWithThreads } from '../lib/thread-tree'

export type LocalChatMessage = {
  id: string
  role: 'user' | 'assistant'
  content: string
}

type MessagesByThread = Record<string, LocalChatMessage[]>

type HydrateOptions = {
  initialUser?: UserResponse | null
  initialAgents?: AgentResponse[] | null
}

type TalariaAppState = {
  accessToken: string | null
  user: UserResponse | null
  agents: AgentResponse[]
  groupedAgents: AgentWithThreads[]
  selectedAgent: AgentResponse | null
  selectedThread: ChatThreadResponse | null
  selectedMessages: LocalChatMessage[]
  isBootstrapping: boolean
  isAuthenticating: boolean
  isSending: boolean
  error: string
  login: () => Promise<void>
  logout: () => Promise<void>
  selectAgent: (agentId: string) => void
  selectThread: (threadId: string) => void
  startNewChat: (agentId?: string | null) => void
  sendMessage: (messageText: string) => Promise<void>
}

function appendMessages(
  existing: MessagesByThread,
  nextMessages: MessagesByThread,
): MessagesByThread {
  return {
    ...existing,
    ...nextMessages,
  }
}

function createMessageId(role: LocalChatMessage['role']): string {
  return (
    globalThis.crypto?.randomUUID?.() ??
    `${role}-${Date.now()}-${Math.random().toString(16).slice(2)}`
  )
}

function createLocalMessage(
  role: LocalChatMessage['role'],
  content: string,
): LocalChatMessage {
  return {
    id: createMessageId(role),
    role,
    content,
  }
}

export function useTalariaApp(): TalariaAppState {
  const [accessToken, setAccessToken] = useState<string | null>(null)
  const [user, setUser] = useState<UserResponse | null>(null)
  const [agents, setAgents] = useState<AgentResponse[]>([])
  const [threads, setThreads] = useState<ChatThreadResponse[]>([])
  const [messagesByThread, setMessagesByThread] = useState<MessagesByThread>({})
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null)
  const [selectedThreadId, setSelectedThreadId] = useState<string | null>(null)
  const [isBootstrapping, setIsBootstrapping] = useState(true)
  const [isAuthenticating, setIsAuthenticating] = useState(false)
  const [isSending, setIsSending] = useState(false)
  const [error, setError] = useState('')

  const groupedAgents = useMemo(
    () => groupThreadsByAgent(agents, threads),
    [agents, threads],
  )
  const selectedAgent = useMemo(
    () => findAgentById(agents, selectedAgentId),
    [agents, selectedAgentId],
  )
  const selectedThread = useMemo(
    () => findThreadById(threads, selectedThreadId),
    [threads, selectedThreadId],
  )
  const selectedMessages = selectedThreadId
    ? messagesByThread[selectedThreadId] ?? []
    : []

  async function hydrateSession(
    token: string,
    { initialUser = null, initialAgents = null }: HydrateOptions = {},
  ): Promise<void> {
    const [mePayload, threadsPayload]: [MeResponse, ChatThreadResponse[]] = await Promise.all([
      initialUser && initialAgents
        ? Promise.resolve({ user: initialUser, agents: initialAgents })
        : unwrapData(getMeMeGet({
            headers: authorizationHeaders(token),
            responseStyle: 'data',
            throwOnError: true,
          })),
      unwrapData(listThreadsThreadsGet({
        headers: authorizationHeaders(token),
        responseStyle: 'data',
        throwOnError: true,
      })),
    ])

    startTransition(() => {
      setAccessToken(token)
      setUser(mePayload.user)
      setAgents(mePayload.agents)
      setThreads(threadsPayload)
      setSelectedAgentId((currentAgentId) => currentAgentId ?? mePayload.agents[0]?.id ?? null)
      setSelectedThreadId((currentThreadId) => currentThreadId ?? threadsPayload[0]?.id ?? null)
      setError('')
    })
  }

  useEffect(() => {
    let ignore = false

    async function bootstrap(): Promise<void> {
      const session = loadSession()
      if (!session?.accessToken) {
        setIsBootstrapping(false)
        return
      }

      try {
        await hydrateSession(session.accessToken)
      } catch {
        clearSession()
        if (!ignore) {
          setError('Session expired. Please sign in again.')
          setAccessToken(null)
          setUser(null)
          setAgents([])
          setThreads([])
          setSelectedAgentId(null)
          setSelectedThreadId(null)
        }
      } finally {
        if (!ignore) {
          setIsBootstrapping(false)
        }
      }
    }

    void bootstrap()

    return () => {
      ignore = true
    }
  }, [])

  async function login(): Promise<void> {
    setIsAuthenticating(true)
    setError('')

    try {
      const idToken = await signInWithGoogle()
      const authPayload = await unwrapData(
        exchangeAuthTokenAuthExchangePost({
          body: { id_token: idToken },
          responseStyle: 'data',
          throwOnError: true,
        }),
      )
      saveSession({ accessToken: authPayload.access_token })
      await hydrateSession(authPayload.access_token, {
        initialUser: authPayload.user,
        initialAgents: authPayload.agents,
      })
    } catch (loginError) {
      setError(getApiErrorMessage(loginError) || 'Login failed')
    } finally {
      setIsAuthenticating(false)
      setIsBootstrapping(false)
    }
  }

  async function logout(): Promise<void> {
    await signOutFromGoogle()
    clearSession()
    setAccessToken(null)
    setUser(null)
    setAgents([])
    setThreads([])
    setMessagesByThread({})
    setSelectedAgentId(null)
    setSelectedThreadId(null)
    setError('')
  }

  function selectAgent(agentId: string): void {
    setSelectedAgentId(agentId)
    const nextThread = threads.find((thread) => thread.agent_id === agentId) ?? null
    setSelectedThreadId(nextThread?.id ?? null)
  }

  function selectThread(threadId: string): void {
    const nextThread = findThreadById(threads, threadId)
    setSelectedThreadId(threadId)
    if (nextThread) {
      setSelectedAgentId(nextThread.agent_id)
    }
  }

  function startNewChat(agentId?: string | null): void {
    const targetAgentId = agentId ?? selectedAgentId ?? agents[0]?.id ?? null
    setSelectedAgentId(targetAgentId)
    setSelectedThreadId(null)
    setError('')
  }

  async function sendMessage(messageText: string): Promise<void> {
    const content = messageText.trim()
    if (!content || !accessToken) {
      return
    }

    const agentId = selectedAgentId ?? agents[0]?.id
    if (!agentId) {
      setError('No agent is available for this chat yet.')
      return
    }

    setIsSending(true)
    setError('')

    try {
      let activeThread = selectedThread
      if (!activeThread) {
        const createdThread = await unwrapData(createThreadThreadsPost({
          body: { agent_id: agentId },
          headers: authorizationHeaders(accessToken),
          responseStyle: 'data',
          throwOnError: true,
        }))
        activeThread = createdThread
        setThreads((currentThreads) => [createdThread, ...currentThreads])
        setSelectedThreadId(createdThread.id)
      }

      if (!activeThread) {
        setError('Unable to create or select a thread for this message.')
        return
      }

      setSelectedAgentId(agentId)
      setMessagesByThread((currentMessages) =>
        appendMessages(currentMessages, {
          [activeThread.id]: [
            ...(currentMessages[activeThread.id] ?? []),
            createLocalMessage('user', content),
          ],
        }),
      )

      const result = await unwrapData(sendMessageThreadsThreadIdMessagesPost({
        path: { thread_id: activeThread.id },
        body: { message: content },
        headers: authorizationHeaders(accessToken),
        responseStyle: 'data',
        throwOnError: true,
      }))

      setThreads((currentThreads) =>
        currentThreads.map((thread) =>
          thread.id === activeThread.id
            ? {
                ...thread,
                title: thread.title === 'New Chat' ? content.slice(0, 80) : thread.title,
                last_message_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
              }
            : thread,
        ),
      )
      setMessagesByThread((currentMessages) =>
        appendMessages(currentMessages, {
          [activeThread.id]: [
            ...(currentMessages[activeThread.id] ?? []),
            createLocalMessage('assistant', result.response_text),
          ],
        }),
      )
    } catch (sendError) {
      setError(getApiErrorMessage(sendError) || 'Message send failed')
    } finally {
      setIsSending(false)
    }
  }

  return {
    accessToken,
    user,
    agents,
    groupedAgents,
    selectedAgent,
    selectedThread,
    selectedMessages,
    isBootstrapping,
    isAuthenticating,
    isSending,
    error,
    login,
    logout,
    selectAgent,
    selectThread,
    startNewChat,
    sendMessage,
  }
}

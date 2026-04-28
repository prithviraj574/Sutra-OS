import { FormEvent, KeyboardEvent, useEffect, useMemo, useState } from 'react'
import {
  AgentMessage,
  AgentSummary,
  SessionSummary,
  createAgent,
  createSession,
  getApiErrorMessage,
  listAgents,
  listMessages,
  listSessions,
  sendMessage,
} from './api/client'
import { env } from './lib/env'
import './App.css'

function textFromMessage(message: AgentMessage): string {
  if (typeof message.content === 'string') {
    return message.content
  }

  if (Array.isArray(message.content)) {
    return message.content
      .map((part) => {
        if ('text' in part && typeof part.text === 'string') {
          return part.text
        }
        if ('type' in part && part.type === 'toolCall' && typeof part.name === 'string') {
          return `Tool call: ${part.name}`
        }
        return ''
      })
      .filter(Boolean)
      .join('\n')
  }

  return ''
}

function App() {
  const [userId, setUserId] = useState(env.defaultUserId)
  const [userInput, setUserInput] = useState(env.defaultUserId)
  const [agents, setAgents] = useState<AgentSummary[]>([])
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [selectedAgentId, setSelectedAgentId] = useState<string>()
  const [selectedSessionId, setSelectedSessionId] = useState<string>()
  const [messages, setMessages] = useState<AgentMessage[]>([])
  const [draft, setDraft] = useState('')
  const [isBootstrapping, setIsBootstrapping] = useState(true)
  const [isCreatingAgent, setIsCreatingAgent] = useState(false)
  const [isCreatingSession, setIsCreatingSession] = useState(false)
  const [isLoadingMessages, setIsLoadingMessages] = useState(false)
  const [isSending, setIsSending] = useState(false)
  const [error, setError] = useState<string>()

  const activeAgent = agents.find((agent) => agent.id === selectedAgentId)
  const activeSession = sessions.find((session) => session.id === selectedSessionId)
  const assistantCount = messages.filter((message) => message.role === 'assistant').length
  const visibleStatus = error ? 'Needs attention' : isSending ? 'Running' : 'Ready'

  const canSend = useMemo(
    () => Boolean(userId.trim() && selectedSessionId && draft.trim()),
    [draft, selectedSessionId, userId],
  )

  useEffect(() => {
    let isCurrent = true

    async function bootstrap() {
      const normalizedUserId = userId.trim()
      if (!normalizedUserId) {
        setAgents([])
        setSessions([])
        setSelectedAgentId(undefined)
        setSelectedSessionId(undefined)
        setMessages([])
        setIsBootstrapping(false)
        return
      }

      setIsBootstrapping(true)
      setError(undefined)

      try {
        let nextAgents = await listAgents(normalizedUserId)
        if (!isCurrent) {
          return
        }

        if (nextAgents.length === 0) {
          const createdAgent = await createAgent(normalizedUserId)
          nextAgents = [createdAgent]
        }

        const nextAgent = sortByUpdated(nextAgents)[0]
        let nextSessions = await listSessions(normalizedUserId, nextAgent.id)
        if (nextSessions.length === 0) {
          const createdSession = await createSession(normalizedUserId, nextAgent.id)
          nextSessions = [
            {
              id: createdSession.session_id,
              user_id: createdSession.user_id,
              agent_id: createdSession.agent_id,
              status: 'active',
              created_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
            },
          ]
        }

        const nextSession = sortByUpdated(nextSessions)[0]
        const response = await listMessages(normalizedUserId, nextSession.id)

        if (!isCurrent) {
          return
        }

        setAgents(sortByUpdated(nextAgents))
        setSelectedAgentId(nextAgent.id)
        setSessions(sortByUpdated(nextSessions))
        setSelectedSessionId(nextSession.id)
        setMessages(response.messages)
      } catch (caught) {
        if (isCurrent) {
          setError(getApiErrorMessage(caught))
          setAgents([])
          setSessions([])
          setSelectedAgentId(undefined)
          setSelectedSessionId(undefined)
          setMessages([])
        }
      } finally {
        if (isCurrent) {
          setIsBootstrapping(false)
        }
      }
    }

    void bootstrap()

    return () => {
      isCurrent = false
    }
  }, [userId])

  async function handleUserSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const normalizedUserId = userInput.trim()
    if (!normalizedUserId || normalizedUserId === userId) {
      return
    }

    setUserId(normalizedUserId)
    setDraft('')
    setMessages([])
    setSessions([])
    setSelectedAgentId(undefined)
    setSelectedSessionId(undefined)
  }

  async function handleCreateAgent() {
    const normalizedUserId = userId.trim()
    if (!normalizedUserId || isCreatingAgent) {
      return
    }

    setIsCreatingAgent(true)
    setError(undefined)

    try {
      const agentNumber = agents.length + 1
      const createdAgent = await createAgent(normalizedUserId, `Workspace agent ${agentNumber}`)
      const createdSession = await createSession(normalizedUserId, createdAgent.id)
      const nextSession = sessionFromCreated(createdSession)
      setAgents((current) => [createdAgent, ...current])
      setSelectedAgentId(createdAgent.id)
      setSessions([nextSession])
      setSelectedSessionId(nextSession.id)
      setMessages([])
    } catch (caught) {
      setError(getApiErrorMessage(caught))
    } finally {
      setIsCreatingAgent(false)
    }
  }

  async function handleSelectAgent(agentId: string) {
    const normalizedUserId = userId.trim()
    if (!normalizedUserId || agentId === selectedAgentId) {
      return
    }

    setSelectedAgentId(agentId)
    setSelectedSessionId(undefined)
    setSessions([])
    setMessages([])
    setIsLoadingMessages(true)
    setError(undefined)

    try {
      let nextSessions = await listSessions(normalizedUserId, agentId)
      if (nextSessions.length === 0) {
        const createdSession = await createSession(normalizedUserId, agentId)
        nextSessions = [sessionFromCreated(createdSession)]
      }
      const nextSession = sortByUpdated(nextSessions)[0]
      const response = await listMessages(normalizedUserId, nextSession.id)

      setSessions(sortByUpdated(nextSessions))
      setSelectedSessionId(nextSession.id)
      setMessages(response.messages)
    } catch (caught) {
      setError(getApiErrorMessage(caught))
    } finally {
      setIsLoadingMessages(false)
    }
  }

  async function handleCreateSession() {
    const normalizedUserId = userId.trim()
    if (!normalizedUserId || !selectedAgentId || isCreatingSession) {
      return
    }

    setIsCreatingSession(true)
    setError(undefined)

    try {
      const createdSession = await createSession(normalizedUserId, selectedAgentId)
      const nextSession = sessionFromCreated(createdSession)
      setSessions((current) => [nextSession, ...current])
      setSelectedSessionId(nextSession.id)
      setMessages([])
    } catch (caught) {
      setError(getApiErrorMessage(caught))
    } finally {
      setIsCreatingSession(false)
    }
  }

  async function handleSelectSession(sessionId: string) {
    const normalizedUserId = userId.trim()
    if (!normalizedUserId || sessionId === selectedSessionId) {
      return
    }

    setSelectedSessionId(sessionId)
    setMessages([])
    setIsLoadingMessages(true)
    setError(undefined)

    try {
      const response = await listMessages(normalizedUserId, sessionId)
      setMessages(response.messages)
    } catch (caught) {
      setError(getApiErrorMessage(caught))
    } finally {
      setIsLoadingMessages(false)
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!canSend || isSending) {
      return
    }

    const content = draft.trim()
    setDraft('')
    setError(undefined)
    setIsSending(true)

    try {
      const response = await sendMessage(selectedSessionId!, userId.trim(), content)
      setMessages((current) => [...current, ...response.messages])
      setSessions((current) =>
        current.map((session) =>
          session.id === selectedSessionId ? { ...session, updated_at: new Date().toISOString() } : session,
        ),
      )
    } catch (caught) {
      setDraft(content)
      setError(getApiErrorMessage(caught))
    } finally {
      setIsSending(false)
    }
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
      event.preventDefault()
      event.currentTarget.form?.requestSubmit()
    }
  }

  return (
    <main className="workspace-shell">
      <aside className="workspace-sidebar">
        <div className="brand-lockup">
          <span className="brand-mark" aria-hidden="true">
            S
          </span>
          <div>
            <p className="ui-text-eyebrow">Agent OS</p>
            <h1 className="workspace-sidebar__title">Runtime desk</h1>
          </div>
        </div>

        <form className="user-switcher" onSubmit={handleUserSubmit}>
          <div className="user-switcher__label">
            <span className="ui-card-label">Signed in as</span>
            <span className="user-switcher__active">{userId}</span>
          </div>
          <div className="field__row">
            <input
              className="field__input"
              id="user-id"
              aria-label="User id"
              value={userInput}
              onChange={(event) => setUserInput(event.target.value)}
            />
            <button className="ui-button-secondary field__button" disabled={!userInput.trim()}>
              Set
            </button>
          </div>
        </form>

        <section className="nav-section nav-section--agents">
          <div className="nav-section__header">
            <div>
              <p className="ui-card-label">Agents</p>
              <p className="nav-section__hint">Personal workspaces</p>
            </div>
            <button
              className="ui-button-secondary nav-section__action"
              disabled={isBootstrapping || isCreatingAgent}
              onClick={handleCreateAgent}
              type="button"
            >
              New
            </button>
          </div>
          <div className="nav-list" aria-label="Agents">
            {agents.map((agent) => (
              <button
                className={`nav-item ${agent.id === selectedAgentId ? 'nav-item--active' : ''}`}
                key={agent.id}
                onClick={() => void handleSelectAgent(agent.id)}
                type="button"
              >
                <span className="nav-item__main">
                  <span className="nav-item__title">{agent.name}</span>
                  <span className="nav-item__badge">{agent.id === selectedAgentId ? 'Active' : 'Agent'}</span>
                </span>
                <span className="nav-item__meta">Updated {formatDate(agent.updated_at)}</span>
              </button>
            ))}
            {isBootstrapping ? <p className="nav-list__empty ui-text-muted">Loading agents...</p> : null}
          </div>
        </section>

        <section className="nav-section nav-section--sessions">
          <div className="nav-section__header">
            <div>
              <p className="ui-card-label">Sessions</p>
              <p className="nav-section__hint">Threads for the selected agent</p>
            </div>
            <button
              className="ui-button-secondary nav-section__action"
              disabled={!selectedAgentId || isBootstrapping || isCreatingSession}
              onClick={handleCreateSession}
              type="button"
            >
              New
            </button>
          </div>
          <div className="nav-list" aria-label="Sessions">
            {sessions.map((session, index) => (
              <button
                className={`nav-item ${session.id === selectedSessionId ? 'nav-item--active' : ''}`}
                key={session.id}
                onClick={() => void handleSelectSession(session.id)}
                type="button"
              >
                <span className="nav-item__main">
                  <span className="nav-item__title">Thread {sessions.length - index}</span>
                  <span className="nav-item__badge">{session.status}</span>
                </span>
                <span className="nav-item__meta">Last activity {formatDate(session.updated_at)}</span>
              </button>
            ))}
            {!isBootstrapping && sessions.length === 0 ? (
              <p className="nav-list__empty ui-text-muted">No sessions yet.</p>
            ) : null}
          </div>
        </section>
      </aside>

      <section className="chat-pane">
        <header className="chat-pane__header ui-surface">
          <div>
            <p className="ui-text-eyebrow">Live session</p>
            <h2 className="chat-pane__title">{activeAgent?.name ?? 'Agent loop'}</h2>
            <p className="chat-pane__meta ui-text-muted">
              {activeSession ? `Session ${shortId(activeSession.id)}` : 'Select or create a session'}
            </p>
          </div>
          <div className="session-stats" aria-label="Session summary">
            <div className="session-stat">
              <span className="session-stat__value">{messages.length}</span>
              <span className="session-stat__label">messages</span>
            </div>
            <div className="session-stat">
              <span className="session-stat__value">{assistantCount}</span>
              <span className="session-stat__label">agent turns</span>
            </div>
            <div className="session-stat session-stat--status">
              <span className="ui-status-dot ui-status-dot--online" aria-hidden="true" />
              <span className="session-stat__label">{visibleStatus}</span>
            </div>
          </div>
        </header>

        {error ? <div className="workspace-banner ui-surface">{error}</div> : null}

        <div className="chat-pane__messages ui-surface" aria-live="polite">
          {isBootstrapping || isLoadingMessages ? (
            <div className="chat-pane__empty">
              <p className="empty-state__title">Preparing workspace</p>
              <p className="ui-text-body ui-text-muted">Loading the selected agent and its thread.</p>
            </div>
          ) : messages.length === 0 ? (
            <div className="chat-pane__empty">
              <p className="empty-state__title">Start the thread</p>
              <p className="ui-text-body ui-text-muted">
                Ask a question, delegate a task, or test the agent loop for this session.
              </p>
            </div>
          ) : (
            messages.map((message, index) => (
              <article
                className={`chat-bubble chat-bubble--${message.role === 'user' ? 'user' : 'assistant'}`}
                key={`${message.role}-${message.timestamp ?? index}-${index}`}
              >
                <span className="chat-bubble__role">{message.role === 'user' ? 'You' : 'Agent'}</span>
                <span>{textFromMessage(message)}</span>
              </article>
            ))
          )}
        </div>

        <form className="chat-composer ui-surface" onSubmit={handleSubmit}>
          <div className="chat-composer__input-wrap">
            <textarea
              className="chat-composer__input"
              value={draft}
              placeholder="Message this agent..."
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={handleComposerKeyDown}
            />
            <p className="chat-composer__hint">Cmd/Ctrl + Enter to send</p>
          </div>
          <button className="ui-button-primary chat-composer__button" disabled={!canSend || isSending}>
            {isSending ? 'Running' : 'Send'}
          </button>
        </form>
      </section>
    </main>
  )
}

function sortByUpdated<T extends { updated_at: string }>(items: T[]): T[] {
  return [...items].sort((left, right) => Date.parse(right.updated_at) - Date.parse(left.updated_at))
}

function sessionFromCreated(created: { session_id: string; agent_id: string; user_id: string }): SessionSummary {
  const now = new Date().toISOString()
  return {
    id: created.session_id,
    user_id: created.user_id,
    agent_id: created.agent_id,
    status: 'active',
    created_at: now,
    updated_at: now,
  }
}

function shortId(id: string): string {
  return id.length > 8 ? id.slice(0, 8) : id
}

function formatDate(value: string): string {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return 'Recent'
  }
  return parsed.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export default App

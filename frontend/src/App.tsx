import { FormEvent, KeyboardEvent, useEffect, useMemo, useState } from 'react'
import {
  Menu,
  MessageSquarePlus,
  Plus,
  Search,
  Send,
  Settings,
  SlidersHorizontal,
  X,
} from 'lucide-react'
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

type CreatedSession = {
  session_id: string
  agent_id: string
  user_id: string
}

type DisplaySession = {
  session: SessionSummary
  label: string
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
  const [searchQuery, setSearchQuery] = useState('')
  const [isSearchOpen, setIsSearchOpen] = useState(false)
  const [isSettingsOpen, setIsSettingsOpen] = useState(false)
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)
  const [isBootstrapping, setIsBootstrapping] = useState(true)
  const [isCreatingAgent, setIsCreatingAgent] = useState(false)
  const [isCreatingSession, setIsCreatingSession] = useState(false)
  const [isLoadingMessages, setIsLoadingMessages] = useState(false)
  const [isSending, setIsSending] = useState(false)
  const [error, setError] = useState<string>()

  const activeAgent = agents.find((agent) => agent.id === selectedAgentId)
  const activeSession = sessions.find((session) => session.id === selectedSessionId)
  const normalizedSearch = searchQuery.trim().toLowerCase()
  const displaySessions = useMemo(
    () =>
      sessions.map((session, index) => ({
        session,
        label: sessionLabel(sessions.length, index),
      })),
    [sessions],
  )
  const visibleSessions = useMemo(
    () =>
      normalizedSearch
        ? displaySessions.filter(({ label }) => label.toLowerCase().includes(normalizedSearch))
        : displaySessions,
    [displaySessions, normalizedSearch],
  )
  const visibleAgents = useMemo(() => {
    if (!normalizedSearch) {
      return agents
    }

    const matchingAgents = agents.filter((agent) => agent.name.toLowerCase().includes(normalizedSearch))
    if (visibleSessions.length > 0 && activeAgent && !matchingAgents.some((agent) => agent.id === activeAgent.id)) {
      return [activeAgent, ...matchingAgents]
    }
    return matchingAgents
  }, [activeAgent, agents, normalizedSearch, visibleSessions.length])
  const canSend = Boolean(userId.trim() && selectedSessionId && draft.trim())

  useEffect(() => {
    let isCurrent = true

    async function bootstrap() {
      const normalizedUserId = userId.trim()
      if (!normalizedUserId) {
        resetWorkspace()
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
          nextAgents = [await createAgent(normalizedUserId)]
        }

        const nextAgent = sortByUpdated(nextAgents)[0]
        let nextSessions = await listSessions(normalizedUserId, nextAgent.id)
        if (nextSessions.length === 0) {
          nextSessions = [sessionFromCreated(await createSession(normalizedUserId, nextAgent.id))]
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
          resetWorkspace()
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

  function resetWorkspace() {
    setAgents([])
    setSessions([])
    setSelectedAgentId(undefined)
    setSelectedSessionId(undefined)
    setMessages([])
  }

  function resetForUser(normalizedUserId: string) {
    setUserId(normalizedUserId)
    setUserInput(normalizedUserId)
    setDraft('')
    setSearchQuery('')
    setIsSettingsOpen(false)
    resetWorkspace()
  }

  async function handleCreateAgent() {
    const normalizedUserId = userId.trim()
    if (!normalizedUserId || isCreatingAgent) {
      return
    }

    setIsCreatingAgent(true)
    setError(undefined)

    try {
      const createdAgent = await createAgent(normalizedUserId, `Agent ${agents.length + 1}`)
      const createdSession = sessionFromCreated(await createSession(normalizedUserId, createdAgent.id))
      setAgents((current) => [createdAgent, ...current])
      setSelectedAgentId(createdAgent.id)
      setSessions([createdSession])
      setSelectedSessionId(createdSession.id)
      setMessages([])
      setIsSidebarOpen(false)
    } catch (caught) {
      setError(getApiErrorMessage(caught))
    } finally {
      setIsCreatingAgent(false)
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
      const createdSession = sessionFromCreated(await createSession(normalizedUserId, selectedAgentId))
      setSessions((current) => [createdSession, ...current])
      setSelectedSessionId(createdSession.id)
      setMessages([])
      setIsSidebarOpen(false)
    } catch (caught) {
      setError(getApiErrorMessage(caught))
    } finally {
      setIsCreatingSession(false)
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
        nextSessions = [sessionFromCreated(await createSession(normalizedUserId, agentId))]
      }
      const sortedSessions = sortByUpdated(nextSessions)
      const nextSession = sortedSessions[0]
      const response = await listMessages(normalizedUserId, nextSession.id)
      setSessions(sortedSessions)
      setSelectedSessionId(nextSession.id)
      setMessages(response.messages)
    } catch (caught) {
      setError(getApiErrorMessage(caught))
    } finally {
      setIsLoadingMessages(false)
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
      setIsSidebarOpen(false)
    } catch (caught) {
      setError(getApiErrorMessage(caught))
    } finally {
      setIsLoadingMessages(false)
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!canSend || isSending || !selectedSessionId) {
      return
    }

    const content = draft.trim()
    setDraft('')
    setError(undefined)
    setIsSending(true)

    try {
      const response = await sendMessage(selectedSessionId, userId.trim(), content)
      setMessages((current) => [...current, ...response.messages])
      setSessions((current) =>
        sortByUpdated(
          current.map((session) =>
            session.id === selectedSessionId ? { ...session, updated_at: new Date().toISOString() } : session,
          ),
        ),
      )
    } catch (caught) {
      setDraft(content)
      setError(getApiErrorMessage(caught))
    } finally {
      setIsSending(false)
    }
  }

  function handleSettingsSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const normalizedUserId = userInput.trim()
    if (!normalizedUserId) {
      return
    }
    if (normalizedUserId === userId) {
      setIsSettingsOpen(false)
      return
    }
    resetForUser(normalizedUserId)
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
      event.preventDefault()
      event.currentTarget.form?.requestSubmit()
    }
  }

  return (
    <main className="app-shell">
      <header className="mobile-topbar">
        <button
          className="ui-icon-button"
          type="button"
          aria-label="Open navigation"
          onClick={() => setIsSidebarOpen(true)}
        >
          <Menu size={18} />
        </button>
        <div className="mobile-topbar__title">
          <span>Sutra-OS</span>
          <small>{activeAgent?.name ?? 'Agent workspace'}</small>
        </div>
      </header>

      <div
        className={`sidebar-backdrop ${isSidebarOpen ? 'sidebar-backdrop--visible' : ''}`}
        onClick={() => setIsSidebarOpen(false)}
      />

      <aside className={`workspace-sidebar ${isSidebarOpen ? 'workspace-sidebar--open' : ''}`}>
        <Sidebar
          agents={visibleAgents}
          sessions={visibleSessions}
          activeAgent={activeAgent}
          selectedAgentId={selectedAgentId}
          selectedSessionId={selectedSessionId}
          searchQuery={searchQuery}
          isSearchOpen={isSearchOpen}
          isBootstrapping={isBootstrapping}
          isCreatingAgent={isCreatingAgent}
          isCreatingSession={isCreatingSession}
          onClose={() => setIsSidebarOpen(false)}
          onCreateAgent={handleCreateAgent}
          onCreateSession={handleCreateSession}
          onOpenSettings={() => setIsSettingsOpen(true)}
          onSearchQueryChange={setSearchQuery}
          onSelectAgent={handleSelectAgent}
          onSelectSession={handleSelectSession}
          onToggleSearch={() => setIsSearchOpen((current) => !current)}
        />
      </aside>

      <section className="chat-workspace">
        <header className="chat-header">
          <div className="chat-header__title">
            <h1>{activeAgent?.name ?? 'Agent workspace'}</h1>
            <p>{activeSession ? `Thread ${shortId(activeSession.id)}` : 'Select a thread'}</p>
          </div>
          <button className="ui-button-secondary chat-header__button" type="button" onClick={handleCreateSession}>
            <MessageSquarePlus size={16} />
            New chat
          </button>
        </header>

        {error ? <div className="workspace-banner">{error}</div> : null}

        <MessageList
          isLoading={isBootstrapping || isLoadingMessages}
          messages={messages}
        />

        <form className="chat-composer" onSubmit={handleSubmit}>
          <textarea
            className="chat-composer__input"
            value={draft}
            placeholder="Message this agent..."
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={handleComposerKeyDown}
          />
          <div className="chat-composer__bar">
            <span className="chat-composer__hint">Cmd/Ctrl + Enter</span>
            <button className="ui-icon-button ui-icon-button--primary" disabled={!canSend || isSending} type="submit">
              {isSending ? <SlidersHorizontal size={18} /> : <Send size={18} />}
            </button>
          </div>
        </form>
      </section>

      {isSettingsOpen ? (
        <SettingsDialog
          activeAgent={activeAgent}
          agentCount={agents.length}
          sessionCount={sessions.length}
          userId={userId}
          userInput={userInput}
          onClose={() => {
            setUserInput(userId)
            setIsSettingsOpen(false)
          }}
          onSubmit={handleSettingsSubmit}
          onUserInputChange={setUserInput}
        />
      ) : null}
    </main>
  )
}

type SidebarProps = {
  agents: AgentSummary[]
  sessions: DisplaySession[]
  activeAgent?: AgentSummary
  selectedAgentId?: string
  selectedSessionId?: string
  searchQuery: string
  isSearchOpen: boolean
  isBootstrapping: boolean
  isCreatingAgent: boolean
  isCreatingSession: boolean
  onClose: () => void
  onCreateAgent: () => void
  onCreateSession: () => void
  onOpenSettings: () => void
  onSearchQueryChange: (value: string) => void
  onSelectAgent: (agentId: string) => void
  onSelectSession: (sessionId: string) => void
  onToggleSearch: () => void
}

function Sidebar({
  agents,
  sessions,
  activeAgent,
  selectedAgentId,
  selectedSessionId,
  searchQuery,
  isSearchOpen,
  isBootstrapping,
  isCreatingAgent,
  isCreatingSession,
  onClose,
  onCreateAgent,
  onCreateSession,
  onOpenSettings,
  onSearchQueryChange,
  onSelectAgent,
  onSelectSession,
  onToggleSearch,
}: SidebarProps) {
  return (
    <>
      <div className="sidebar-titlebar">
        <div className="product-mark">S</div>
        <div className="product-copy">
          <strong>Sutra-OS</strong>
          <span>Agent runtime</span>
        </div>
        <button className="ui-icon-button sidebar-titlebar__close" type="button" aria-label="Close navigation" onClick={onClose}>
          <X size={18} />
        </button>
      </div>

      <nav className="sidebar-actions" aria-label="Workspace actions">
        <button className="sidebar-action" type="button" disabled={!activeAgent || isCreatingSession} onClick={onCreateSession}>
          <MessageSquarePlus size={17} />
          <span>New chat</span>
        </button>
        <button className="sidebar-action" type="button" onClick={onToggleSearch}>
          <Search size={17} />
          <span>Search</span>
        </button>
      </nav>

      {isSearchOpen ? (
        <label className="sidebar-search">
          <Search size={15} />
          <input
            autoFocus
            value={searchQuery}
            placeholder="Search agents and sessions"
            onChange={(event) => onSearchQueryChange(event.target.value)}
          />
        </label>
      ) : null}

      <section className="sidebar-section">
        <div className="sidebar-section__header">
          <span>Agents</span>
          <button
            className="ui-icon-button ui-icon-button--quiet"
            type="button"
            aria-label="Create agent"
            disabled={isCreatingAgent}
            onClick={onCreateAgent}
          >
            <Plus size={16} />
          </button>
        </div>

        <div className="sidebar-list" aria-label="Agents">
          {agents.map((agent) => (
            <div className="agent-group" key={agent.id}>
              <button
                className={`agent-row ${agent.id === selectedAgentId ? 'agent-row--active' : ''}`}
                type="button"
                onClick={() => void onSelectAgent(agent.id)}
              >
                <span>{agent.name}</span>
                <small>{formatRelative(agent.updated_at)}</small>
              </button>

              {agent.id === selectedAgentId ? (
                <div className="session-list" aria-label={`${agent.name} sessions`}>
                  {sessions.map(({ session, label }) => (
                    <button
                      className={`session-row ${session.id === selectedSessionId ? 'session-row--active' : ''}`}
                      key={session.id}
                      type="button"
                      onClick={() => void onSelectSession(session.id)}
                    >
                      <span>{label}</span>
                      <small>{formatRelative(session.updated_at)}</small>
                    </button>
                  ))}
                  {!isBootstrapping && sessions.length === 0 ? (
                    <p className="sidebar-empty">No sessions</p>
                  ) : null}
                </div>
              ) : null}
            </div>
          ))}

          {isBootstrapping ? <p className="sidebar-empty">Loading workspace...</p> : null}
          {!isBootstrapping && agents.length === 0 ? <p className="sidebar-empty">No agents found</p> : null}
        </div>
      </section>

      <div className="sidebar-footer">
        <button className="sidebar-action" type="button" onClick={onOpenSettings}>
          <Settings size={17} />
          <span>Settings</span>
        </button>
      </div>
    </>
  )
}

function MessageList({ isLoading, messages }: { isLoading: boolean; messages: AgentMessage[] }) {
  if (isLoading) {
    return (
      <div className="message-stage" aria-live="polite">
        <div className="empty-thread">
          <span className="empty-thread__mark" />
          <h2>Preparing workspace</h2>
          <p>Loading the selected agent and thread.</p>
        </div>
      </div>
    )
  }

  if (messages.length === 0) {
    return (
      <div className="message-stage" aria-live="polite">
        <div className="empty-thread">
          <span className="empty-thread__mark" />
          <h2>Start the thread</h2>
          <p>Ask a question, test a tool call, or sketch the next runtime behavior.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="message-stage" aria-live="polite">
      <div className="message-column">
        {messages.map((message, index) => (
          <article
            className={`message-bubble message-bubble--${message.role === 'user' ? 'user' : 'assistant'}`}
            key={`${message.role}-${message.timestamp ?? index}-${index}`}
          >
            <span className="message-bubble__role">{labelForRole(message.role)}</span>
            <span>{textFromMessage(message)}</span>
          </article>
        ))}
      </div>
    </div>
  )
}

type SettingsDialogProps = {
  activeAgent?: AgentSummary
  agentCount: number
  sessionCount: number
  userId: string
  userInput: string
  onClose: () => void
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
  onUserInputChange: (value: string) => void
}

function SettingsDialog({
  activeAgent,
  agentCount,
  sessionCount,
  userId,
  userInput,
  onClose,
  onSubmit,
  onUserInputChange,
}: SettingsDialogProps) {
  return (
    <div className="settings-backdrop" role="presentation" onClick={onClose}>
      <section
        className="settings-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-title"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="settings-panel__header">
          <div>
            <p className="ui-text-eyebrow">Runtime settings</p>
            <h2 id="settings-title">Workspace identity</h2>
          </div>
          <button className="ui-icon-button" type="button" aria-label="Close settings" onClick={onClose}>
            <X size={18} />
          </button>
        </header>

        <form className="settings-form" onSubmit={onSubmit}>
          <label className="settings-field">
            <span>User ID</span>
            <input value={userInput} onChange={(event) => onUserInputChange(event.target.value)} />
          </label>
          <button className="ui-button-primary" disabled={!userInput.trim()} type="submit">
            Apply
          </button>
        </form>

        <dl className="runtime-facts">
          <div>
            <dt>Current user</dt>
            <dd>{userId}</dd>
          </div>
          <div>
            <dt>Active agent</dt>
            <dd>{activeAgent?.name ?? 'None'}</dd>
          </div>
          <div>
            <dt>Loaded agents</dt>
            <dd>{agentCount}</dd>
          </div>
          <div>
            <dt>Loaded sessions</dt>
            <dd>{sessionCount}</dd>
          </div>
        </dl>
      </section>
    </div>
  )
}

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

function sortByUpdated<T extends { updated_at: string }>(items: T[]): T[] {
  return [...items].sort((left, right) => Date.parse(right.updated_at) - Date.parse(left.updated_at))
}

function sessionFromCreated(created: CreatedSession): SessionSummary {
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

function sessionLabel(total: number, index: number): string {
  return `Thread ${total - index}`
}

function shortId(id: string): string {
  return id.length > 8 ? id.slice(0, 8) : id
}

function labelForRole(role: AgentMessage['role']): string {
  if (role === 'user') {
    return 'You'
  }
  if (role === 'toolResult') {
    return 'Tool'
  }
  return 'Agent'
}

function formatRelative(value: string): string {
  const timestamp = Date.parse(value)
  if (Number.isNaN(timestamp)) {
    return 'recent'
  }

  const diffMs = Date.now() - timestamp
  const minute = 60_000
  const hour = 60 * minute
  const day = 24 * hour

  if (diffMs < minute) {
    return 'now'
  }
  if (diffMs < hour) {
    return `${Math.floor(diffMs / minute)}m`
  }
  if (diffMs < day) {
    return `${Math.floor(diffMs / hour)}h`
  }
  return `${Math.floor(diffMs / day)}d`
}

export default App

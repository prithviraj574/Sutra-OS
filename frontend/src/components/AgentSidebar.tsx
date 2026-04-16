import type { UserResponse } from '../api/generated'
import type { AgentWithThreads } from '../lib/thread-tree'

type AgentSidebarProps = {
  groupedAgents: AgentWithThreads[]
  selectedAgentId: string | null
  selectedThreadId: string | null
  user: UserResponse | null
  onSelectAgent: (agentId: string) => void
  onSelectThread: (threadId: string) => void
  onStartNewChat: (agentId?: string | null) => void
  onLogout: () => void
}

function AgentSidebar({
  groupedAgents,
  selectedAgentId,
  selectedThreadId,
  user,
  onSelectAgent,
  onSelectThread,
  onStartNewChat,
  onLogout,
}: AgentSidebarProps) {
  return (
    <aside className="workspace-sidebar ui-surface ui-surface--raised">
      <div className="workspace-sidebar__header">
        <div>
          <p className="ui-text-eyebrow">Workspace</p>
          <h2 className="workspace-sidebar__title">{user?.name || user?.email || 'Talaria'}</h2>
        </div>
        <button className="sidebar-ghost-button" type="button" onClick={onLogout}>
          Logout
        </button>
      </div>

      <button
        className="ui-button-primary sidebar-new-chat"
        type="button"
        onClick={() => onStartNewChat(selectedAgentId)}
      >
        New Chat
      </button>

      <div className="workspace-sidebar__groups">
        {groupedAgents.map((agent) => (
          <section key={agent.id} className="agent-group">
            <button
              className={`agent-group__trigger ${
                agent.id === selectedAgentId ? 'agent-group__trigger--active' : ''
              }`}
              type="button"
              onClick={() => onSelectAgent(agent.id)}
            >
              <span>{agent.name}</span>
              <span className="agent-group__count">{agent.threads.length}</span>
            </button>

            <div className="agent-group__threads">
              {agent.threads.length ? (
                agent.threads.map((thread) => (
                  <button
                    key={thread.id}
                    className={`thread-link ${
                      thread.id === selectedThreadId ? 'thread-link--active' : ''
                    }`}
                    type="button"
                    onClick={() => onSelectThread(thread.id)}
                  >
                    {thread.title}
                  </button>
                ))
              ) : (
                <p className="thread-link thread-link--empty">No threads yet</p>
              )}
            </div>
          </section>
        ))}
      </div>
    </aside>
  )
}

export default AgentSidebar

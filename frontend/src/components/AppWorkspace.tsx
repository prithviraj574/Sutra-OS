import AgentSidebar from './AgentSidebar'
import ChatPane from './ChatPane'
import type {
  AgentResponse,
  ChatThreadResponse,
  UserResponse,
} from '../api/generated'
import type { LocalChatMessage } from '../hooks/useTalariaApp'
import type { AgentWithThreads } from '../lib/thread-tree'

type AppWorkspaceProps = {
  error: string
  groupedAgents: AgentWithThreads[]
  selectedAgent: AgentResponse | null
  selectedThread: ChatThreadResponse | null
  selectedMessages: LocalChatMessage[]
  user: UserResponse | null
  isSending: boolean
  onLogout: () => Promise<void>
  onSelectAgent: (agentId: string) => void
  onSelectThread: (threadId: string) => void
  onSendMessage: (messageText: string) => Promise<void>
  onStartNewChat: (agentId?: string | null) => void
}

function AppWorkspace({
  error,
  groupedAgents,
  selectedAgent,
  selectedThread,
  selectedMessages,
  user,
  isSending,
  onLogout,
  onSelectAgent,
  onSelectThread,
  onSendMessage,
  onStartNewChat,
}: AppWorkspaceProps) {
  return (
    <main className="workspace-shell">
      <AgentSidebar
        groupedAgents={groupedAgents}
        selectedAgentId={selectedAgent?.id ?? null}
        selectedThreadId={selectedThread?.id ?? null}
        user={user}
        onSelectAgent={onSelectAgent}
        onSelectThread={onSelectThread}
        onStartNewChat={onStartNewChat}
        onLogout={() => {
          void onLogout()
        }}
      />

      <div className="workspace-main">
        {error ? (
          <section className="workspace-banner ui-surface ui-surface--raised" role="alert">
            <p className="ui-text-body ui-text-muted">{error}</p>
          </section>
        ) : null}

        <ChatPane
          selectedAgent={selectedAgent}
          selectedThread={selectedThread}
          messages={selectedMessages}
          isSending={isSending}
          onSendMessage={onSendMessage}
          onStartNewChat={onStartNewChat}
        />
      </div>
    </main>
  )
}

export default AppWorkspace

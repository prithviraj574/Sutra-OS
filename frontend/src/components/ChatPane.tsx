import { useState, type FormEvent } from 'react'
import type { AgentResponse, ChatThreadResponse } from '../api/generated'
import type { LocalChatMessage } from '../hooks/useTalariaApp'

type ChatPaneProps = {
  selectedAgent: AgentResponse | null
  selectedThread: ChatThreadResponse | null
  messages: LocalChatMessage[]
  isSending: boolean
  onSendMessage: (messageText: string) => Promise<void>
  onStartNewChat: (agentId?: string | null) => void
}

function ChatPane({
  selectedAgent,
  selectedThread,
  messages,
  isSending,
  onSendMessage,
  onStartNewChat,
}: ChatPaneProps) {
  const [draft, setDraft] = useState('')

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault()
    const nextDraft = draft.trim()
    if (!nextDraft || isSending) {
      return
    }

    setDraft('')
    await onSendMessage(nextDraft)
  }

  return (
    <section className="chat-pane ui-surface ui-surface--raised">
      <header className="chat-pane__header">
        <div>
          <p className="ui-text-eyebrow">Chat</p>
          <h2 className="chat-pane__title">
            {selectedThread?.title || selectedAgent?.name || 'Choose an agent'}
          </h2>
          <p className="ui-text-body ui-text-muted">
            {selectedThread
              ? 'Minimal chat for now. We will deepen this interface next.'
              : 'Start a new conversation under the selected agent.'}
          </p>
        </div>

        <button
          className="sidebar-ghost-button"
          type="button"
          onClick={() => onStartNewChat(selectedAgent?.id)}
        >
          Clear Thread
        </button>
      </header>

      <div className="chat-pane__messages">
        {messages.length ? (
          messages.map((message) => (
            <article
              key={message.id}
              className={`chat-bubble ${
                message.role === 'user' ? 'chat-bubble--user' : 'chat-bubble--assistant'
              }`}
            >
              {message.content}
            </article>
          ))
        ) : (
          <div className="chat-pane__empty">
            <p className="ui-text-body ui-text-muted">
              Pick a thread or send the first message to open a new one.
            </p>
          </div>
        )}
      </div>

      <form className="chat-composer" onSubmit={handleSubmit}>
        <textarea
          className="chat-composer__input"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Message your selected agent..."
          rows={4}
        />
        <button className="ui-button-primary chat-composer__button" type="submit">
          {isSending ? 'Sending...' : 'Send'}
        </button>
      </form>
    </section>
  )
}

export default ChatPane

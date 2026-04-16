import AppWorkspace from './components/AppWorkspace'
import LoginScreen from './components/LoginScreen'
import { useTalariaApp } from './hooks/useTalariaApp'
import './App.css'

function App() {
  const app = useTalariaApp()

  if (app.isBootstrapping) {
    return (
      <main className="auth-screen">
        <section className="auth-card ui-surface ui-surface--hero">
          <p className="ui-text-eyebrow">Talaria</p>
          <h1 className="ui-text-display auth-title">Loading your workspace...</h1>
        </section>
      </main>
    )
  }

  if (!app.accessToken) {
    return (
      <LoginScreen
        isLoading={app.isAuthenticating}
        error={app.error}
        onLogin={() => {
          void app.login()
        }}
      />
    )
  }

  return (
    <AppWorkspace
      error={app.error}
      groupedAgents={app.groupedAgents}
      selectedAgent={app.selectedAgent}
      selectedThread={app.selectedThread}
      selectedMessages={app.selectedMessages}
      user={app.user}
      isSending={app.isSending}
      onLogout={app.logout}
      onSelectAgent={app.selectAgent}
      onSelectThread={app.selectThread}
      onSendMessage={app.sendMessage}
      onStartNewChat={app.startNewChat}
    />
  )
}

export default App

import type { MouseEventHandler } from 'react'

type LoginScreenProps = {
  isLoading: boolean
  error: string
  onLogin: MouseEventHandler<HTMLButtonElement>
}

function LoginScreen({ isLoading, error, onLogin }: LoginScreenProps) {
  return (
    <main className="auth-screen">
      <section className="auth-card ui-surface ui-surface--hero">
        <p className="ui-text-eyebrow">Talaria</p>
        <h1 className="ui-text-display auth-title">
          Sign in once and step into your agents.
        </h1>
        <p className="ui-text-body ui-text-body--lead ui-text-muted auth-copy">
          Start with Google, then land directly in a lightweight agent-first chat
          workspace.
        </p>

        <button
          className="ui-button-primary auth-button"
          type="button"
          onClick={onLogin}
          disabled={isLoading}
        >
          {isLoading ? 'Signing in...' : 'Login with Google'}
        </button>

        {error ? (
          <p className="ui-text-body ui-text-muted auth-error" role="alert">
            {error}
          </p>
        ) : null}
      </section>
    </main>
  )
}

export default LoginScreen

type SessionRecord = {
  accessToken: string
}

const SESSION_KEY = 'talaria.session'

export function loadSession(): SessionRecord | null {
  const raw = window.localStorage.getItem(SESSION_KEY)
  if (!raw) {
    return null
  }

  try {
    const parsed: unknown = JSON.parse(raw)
    if (
      !parsed ||
      typeof parsed !== 'object' ||
      typeof (parsed as { accessToken?: unknown }).accessToken !== 'string'
    ) {
      return null
    }
    return { accessToken: (parsed as { accessToken: string }).accessToken }
  } catch {
    return null
  }
}

export function saveSession(session: SessionRecord): void {
  window.localStorage.setItem(SESSION_KEY, JSON.stringify(session))
}

export function clearSession(): void {
  window.localStorage.removeItem(SESSION_KEY)
}

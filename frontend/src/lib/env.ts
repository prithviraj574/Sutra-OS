type MaybeString = string | undefined

function trim(value: MaybeString): string {
  return value?.trim() ?? ''
}

export const env = {
  apiBaseUrl: trim(import.meta.env.VITE_API_BASE_URL) || 'http://localhost:8000',
  firebaseApiKey: trim(import.meta.env.VITE_FIREBASE_API_KEY),
  firebaseAuthDomain: trim(import.meta.env.VITE_FIREBASE_AUTH_DOMAIN),
  firebaseProjectId: trim(import.meta.env.VITE_FIREBASE_PROJECT_ID),
  firebaseAppId: trim(import.meta.env.VITE_FIREBASE_APP_ID),
} as const

export function isFirebaseConfigured(): boolean {
  return Boolean(
    env.firebaseApiKey &&
      env.firebaseAuthDomain &&
      env.firebaseProjectId &&
      env.firebaseAppId,
  )
}

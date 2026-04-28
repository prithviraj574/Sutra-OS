type MaybeString = string | undefined

function trim(value: MaybeString): string {
  return value?.trim() ?? ''
}

export const env = {
  apiBaseUrl: trim(import.meta.env.VITE_API_BASE_URL) || 'http://localhost:8000',
  defaultUserId: trim(import.meta.env.VITE_DEFAULT_USER_ID) || 'local-user',
} as const

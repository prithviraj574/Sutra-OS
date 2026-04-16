import { client } from './generated/client.gen'
import { env } from '../lib/env'

client.setConfig({
  baseUrl: env.apiBaseUrl,
})

export function authorizationHeaders(accessToken: string) {
  return {
    authorization: `Bearer ${accessToken}`,
  }
}

export function getApiErrorMessage(error: unknown): string {
  if (typeof error === 'string' && error.trim()) {
    return error
  }

  if (error && typeof error === 'object' && 'detail' in error) {
    const detail = (error as { detail?: unknown }).detail
    if (typeof detail === 'string' && detail.trim()) {
      return detail
    }
  }

  if (error instanceof Error) {
    return error.message
  }

  return 'Unexpected request failure'
}

export async function unwrapData<T>(
  promise: Promise<T | { data: T }>,
): Promise<T> {
  const result = await promise

  if (
    result &&
    typeof result === 'object' &&
    'data' in result
  ) {
    return result.data
  }

  return result
}

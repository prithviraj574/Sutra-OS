import '@testing-library/jest-dom/vitest'

if (typeof window !== 'undefined' && typeof window.localStorage?.getItem !== 'function') {
  let storage: Record<string, string> = {}

  Object.defineProperty(window, 'localStorage', {
    value: {
      getItem(key: string): string | null {
        return Object.prototype.hasOwnProperty.call(storage, key) ? storage[key] : null
      },
      setItem(key: string, value: string): void {
        storage[key] = String(value)
      },
      removeItem(key: string): void {
        delete storage[key]
      },
      clear(): void {
        storage = {}
      },
    },
    configurable: true,
  })
}

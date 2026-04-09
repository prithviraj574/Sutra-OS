import { useEffect, useState } from 'react'
import './App.css'

function App() {
  const [health, setHealth] = useState('Checking...')
  const [message, setMessage] = useState('Loading...')

  useEffect(() => {
    const apiBaseUrl =
      import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

    const load = async () => {
      try {
        const [healthRes, messageRes] = await Promise.all([
          fetch(`${apiBaseUrl}/health`),
          fetch(`${apiBaseUrl}/api/message`),
        ])

        const healthJson = await healthRes.json()
        const messageJson = await messageRes.json()

        setHealth(healthJson.status ?? 'unknown')
        setMessage(messageJson.message ?? 'No message')
      } catch (_error) {
        setHealth('offline')
        setMessage('Unable to reach backend')
      }
    }

    load()
  }, [])

  return (
    <main>
      <h1>Sutra OS Webapp</h1>
      <p className="subtitle">React frontend connected to FastAPI backend</p>
      <section className="card">
        <p>
          <strong>Backend health:</strong> {health}
        </p>
        <p>
          <strong>Message:</strong> {message}
        </p>
      </section>
    </main>
  )
}

export default App

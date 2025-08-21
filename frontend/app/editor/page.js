'use client'

import { useState } from 'react'

export default function Editor() {
  const [prompt, setPrompt] = useState('Write a small Python function')
  const [out, setOut] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function run() {
    setLoading(true)
    setError(null)
    setOut('')
    try {
      const res = await fetch('/api/agent/invoke_tool', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tool: 'generate_code', payload: { prompt }, persona: 'coder' })
      })
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({ detail: `HTTP error! status: ${res.status}` }))
        throw new Error(errorData.detail)
      }
      const j = await res.json()
      setOut(JSON.stringify(j, null, 2))
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ padding: 20, background: '#071025', color: '#e6eef8' }}>
      <h1>Editor (App Router)</h1>
      <textarea
        value={prompt}
        onChange={e => setPrompt(e.target.value)}
        style={{ width: '100%', height: 160, background: '#1e293b', color: 'white', border: '1px solid #374151' }}
        disabled={loading}
      />
      <div style={{ marginTop: 8 }}>
        <button
          onClick={run}
          style={{ padding: '8px 16px', background: '#10b981', border: 'none', borderRadius: 4, cursor: 'pointer', opacity: loading ? 0.5 : 1 }}
          disabled={loading}
        >
          {loading ? 'Running...' : 'Run'}
        </button>
      </div>
      {error && <pre style={{ color: '#f87171', marginTop: 8 }}>Error: {error}</pre>}
      {out && <pre style={{ marginTop: 8, background: '#111827', padding: 12, borderRadius: 4 }}>{out}</pre>}
    </div>
  )
}

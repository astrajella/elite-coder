import React, { useEffect, useState } from 'react'
import dynamic from 'next/dynamic'

export default function Home() {
  const [stats, setStats] = useState(null)

  useEffect(() => {
    fetch('/api/ledger/stats')
      .then(r => r.json())
      .then(j => setStats(j))
      .catch(() => {})
  }, [])

  return (
    <div style={{ background: '#0f172a', color: '#e6eef8', minHeight: '100vh', padding: 20 }}>
      <h1>AI Code Agent — Next-grade Frontend</h1>
      <div style={{ marginTop: 10 }}>
        <a href='/dashboard' style={{ color: '#7dd3fc', marginRight: 20 }}>Dashboard</a>
        <a href='/monaco' style={{ color: '#7dd3fc' }}>Monaco Diff</a>
      </div>
      <div style={{ display: 'flex', gap: 20 }}>
        <div style={{ flex: 1 }}>
          <h2>Persona Stats</h2>
          <pre>{JSON.stringify(stats, null, 2)}</pre>
        </div>
        <div style={{ width: 420 }}>
          <h2>Actions</h2>
          <a href="/editor" style={{ color: '#7dd3fc' }}>Open Editor</a>
          <a href='/artifacts' style={{ color: '#7dd3fc', marginLeft: 20 }}>Artifacts</a>
        </div>
      </div>
    </div>
  )
}

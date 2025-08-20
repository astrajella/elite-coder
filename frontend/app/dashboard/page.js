'use client'

import { useEffect, useState } from 'react'

export default function Dashboard() {
  const [stats, setStats] = useState(null)

  useEffect(() => {
    fetch('/api/ledger/stats')
      .then(r => r.json())
      .then(j => setStats(j))
      .catch(() => {})
  }, [])

  return (
    <div style={{ padding: 20, background: '#071025', color: '#e6eef8' }}>
      <h1>Dashboard</h1>
      <pre>{JSON.stringify(stats, null, 2)}</pre>
    </div>
  )
}

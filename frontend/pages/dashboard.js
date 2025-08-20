import React, { useEffect, useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line, Legend } from 'recharts'

export default function Dashboard() {
  const [stats, setStats] = useState({ persona: {}, tool: {}, totals: {} })
  const [daily, setDaily] = useState([])

  useEffect(() => {
    fetch('/api/ledger/stats')
      .then(r => r.json())
      .then(j => setStats(j))
      .catch(() => {})
    fetch('/api/ledger/daily')
      .then(r => r.json())
      .then(j => setDaily(j.daily || []))
      .catch(() => {})
    const es = new EventSource('/api/ledger/stream')
    es.onmessage = (e) => {
      try {
        const d = JSON.parse(e.data)
        setStats(d)
        fetch('/api/ledger/daily')
          .then(r => r.json())
          .then(j => setDaily(j.daily || []))
      } catch (err) {}
    }
    return () => es.close()
  }, [])

  const dailyData = daily.map(d => ({ date: d.date, cost: d.total_cost, tokens: d.total_tokens }))

  return (
    <div style={{ padding: 20, background: '#071025', color: '#e6eef8', minHeight: '100vh' }}>
      <h1>Analytics Dashboard</h1>
      <div style={{ display: 'flex', gap: 20 }}>
        <div style={{ flex: 1 }}>
          <h3>Daily Cost</h3>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={dailyData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" />
              <YAxis />
              <Tooltip />
              <Bar dataKey="cost" fill="#8884d8" />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div style={{ flex: 1 }}>
          <h3>Daily Tokens</h3>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={dailyData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" />
              <YAxis />
              <Tooltip />
              <Bar dataKey="tokens" fill="#82ca9d" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
      <div style={{ marginTop: 20 }}>
        <h3>Persona Totals</h3>
        <pre>{JSON.stringify(stats.persona, null, 2)}</pre>
      </div>
    </div>
  )
}

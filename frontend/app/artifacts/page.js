'use client'

import { useEffect, useState } from 'react'

export default function Artifacts() {
  const [arts, setArts] = useState([])

  useEffect(() => {
    fetch('/api/agent/artifacts')
      .then(r => r.json())
      .then(j => setArts(j.artifacts || []))
      .catch(() => {})
  }, [])

  return (
    <div style={{ padding: 20, background: '#071025', color: '#e6eef8' }}>
      <h1>Artifacts</h1>
      <ul>
        {arts.map(a => (
          <li key={a.name}>
            <a href={'/api/agent/artifacts/download?name=' + encodeURIComponent(a.path)}>{a.name}</a>
          </li>
        ))}
      </ul>
    </div>
  )
}

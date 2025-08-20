'use client'

import dynamic from 'next/dynamic'
import { useState } from 'react'
const Editor = dynamic(() => import('@monaco-editor/react'), { ssr: false })

export default function Monaco() {
  const [modified, setModified] = useState('def add(a,b):\n  return a+b\n')

  async function commit() {
    const res = await fetch('/api/agent/commit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ commit_message: 'Edit', patches: [{ path: 'src/math.py', type: 'replace', content: modified }] })
    })
    const j = await res.json()
    alert(JSON.stringify(j))
  }

  return (
    <div style={{ padding: 20, background: '#071025', color: '#e6eef8' }}>
      <h1>Monaco (App Router)</h1>
      <Editor width='100%' height={400} language='python' value={modified} onChange={v => setModified(v)} />
      <div>
        <button onClick={commit}>Commit</button>
      </div>
    </div>
  )
}

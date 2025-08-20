import dynamic from 'next/dynamic'
import React, { useState } from 'react'
const Editor = dynamic(() => import('@monaco-editor/react'), { ssr: false })

export default function MonacoPage() {
  const [original, setOriginal] = useState("def add(a,b):\n    return a + b\n")
  const [modified, setModified] = useState("def add_numbers(a,b):\n    # improved name\n    return a + b\n")
  const [msg, setMsg] = useState('')

  async function commitPatches() {
    const token = (typeof window !== 'undefined' && localStorage.getItem('ai_token')) || process.env.NEXT_PUBLIC_DEV_TOKEN || null
    const patches = [{ path: 'src/utils/math.py', type: 'replace', content: modified }]
    const res = await fetch('/api/agent/commit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token },
      body: JSON.stringify({ commit_message: 'Improve add naming', patches })
    })
    const j = await res.json()
    setMsg(JSON.stringify(j, null, 2))
  }

  return (
    <div style={{ background: '#0b1220', color: '#e6eef8', minHeight: '100vh', padding: 20 }}>
      <h1>Monaco Diff + Commit</h1>
      <div style={{ display: 'flex', gap: 20 }}>
        <div style={{ flex: 1 }}>
          <h3>Original</h3>
          <Editor width='100%' height={360} language='python' value={original} onChange={v => setOriginal(v)} />
        </div>
        <div style={{ flex: 1 }}>
          <h3>Modified</h3>
          <Editor width='100%' height={360} language='python' value={modified} onChange={v => setModified(v)} />
        </div>
      </div>
      <div style={{ marginTop: 12 }}>
        <button onClick={commitPatches} style={{ padding: 8, background: '#06b6d4', borderRadius: 6 }}>Commit Patches</button>
      </div>
      <pre style={{ marginTop: 20 }}>{msg}</pre>
    </div>
  )
}

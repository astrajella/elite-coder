import React, { useState } from 'react'

export default function Login() {
  const [user, setUser] = useState('dev')
  const [pw, setPw] = useState('pass')
  const [msg, setMsg] = useState('')

  async function doLogin() {
    const form = new URLSearchParams()
    form.append('username', user)
    form.append('password', pw)
    const res = await fetch('/api/agent/auth/login', { method: 'POST', body: form })
    if (!res.ok) {
      setMsg('login failed')
      return
    }
    const j = await res.json()
    localStorage.setItem('ai_token', j.access_token)
    setMsg('ok')
  }

  return (
    <div style={{ padding: 20, background: '#071025', color: '#e6eef8' }}>
      <h1>Login</h1>
      <div>
        <input value={user} onChange={e => setUser(e.target.value)} />
      </div>
      <div>
        <input type='password' value={pw} onChange={e => setPw(e.target.value)} />
      </div>
      <div>
        <button onClick={doLogin}>Login</button>
      </div>
      <div>{msg}</div>
    </div>
  )
}

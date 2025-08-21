import React, { useState } from 'react'
import { useRouter } from 'next/router'

export default function Login() {
  const [user, setUser] = useState('dev')
  const [pw, setPw] = useState('pass')
  const [msg, setMsg] = useState('')
  const [loading, setLoading] = useState(false)
  const router = useRouter()

  async function doLogin() {
    setLoading(true)
    setMsg('')
    try {
      const form = new URLSearchParams()
      form.append('username', user)
      form.append('password', pw)
      const res = await fetch('/api/agent/auth/login', { method: 'POST', body: form })
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({ detail: 'Login failed' }))
        throw new Error(errorData.detail)
      }
      const j = await res.json()
      localStorage.setItem('ai_token', j.access_token)
      setMsg('Login successful! Redirecting...')
      router.push('/dashboard')
    } catch (e) {
      setMsg(e.message)
    } finally {
      setLoading(false)
    }
  }

  const handleKeyPress = (event) => {
    if (event.key === 'Enter') {
      doLogin()
    }
  }

  return (
    <div style={{ padding: 20, background: '#071025', color: '#e6eef8', height: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ background: '#111827', padding: '40px', borderRadius: '8px', width: '320px' }}>
        <h1 style={{ textAlign: 'center', marginBottom: '24px' }}>Login</h1>
        <div style={{ marginBottom: '16px' }}>
          <label style={{ display: 'block', marginBottom: '8px' }}>Username</label>
          <input
            value={user}
            onChange={e => setUser(e.target.value)}
            onKeyPress={handleKeyPress}
            style={{ width: '100%', padding: '8px', background: '#1e293b', border: '1px solid #374151', color: 'white' }}
            disabled={loading}
          />
        </div>
        <div style={{ marginBottom: '24px' }}>
          <label style={{ display: 'block', marginBottom: '8px' }}>Password</label>
          <input
            type='password'
            value={pw}
            onChange={e => setPw(e.target.value)}
            onKeyPress={handleKeyPress}
            style={{ width: '100%', padding: '8px', background: '#1e293b', border: '1px solid #374151', color: 'white' }}
            disabled={loading}
          />
        </div>
        <div>
          <button
            onClick={doLogin}
            style={{ width: '100%', padding: '10px', background: '#10b981', border: 'none', borderRadius: 4, cursor: 'pointer', opacity: loading ? 0.5 : 1 }}
            disabled={loading}
          >
            {loading ? 'Logging in...' : 'Login'}
          </button>
        </div>
        {msg && <div style={{ marginTop: '16px', textAlign: 'center', color: msg.includes('failed') ? '#f87171' : '#34d399' }}>{msg}</div>}
      </div>
    </div>
  )
}

import Link from 'next/link'

export default async function Page() {
  // Use server-side fetch to get stats via Next API proxy
  let stats = null
  try {
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:3000'}/api/ledger/stats`, { cache: 'no-store' })
    if (res.ok) stats = await res.json()
  } catch (e) {}

  return (
    <main style={{ padding: 20, background: '#071025', color: '#e6eef8', minHeight: '100vh' }}>
      <h1>AI Code Agent — App Router Home</h1>
      <div style={{ marginTop: 10 }}>
        <Link href="/dashboard" style={{ color: '#7dd3fc' }}>Dashboard</Link> |{' '}
        <Link href="/editor" style={{ color: '#7dd3fc' }}>Editor</Link> |{' '}
        <Link href="/monaco" style={{ color: '#7dd3fc' }}>Monaco</Link> |{' '}
        <Link href="/artifacts" style={{ color: '#7dd3fc' }}>Artifacts</Link> |{' '}
        <Link href="/rag" style={{ color: '#7dd3fc' }}>RAG Demo</Link> |{' '}
        <Link href="/login" style={{ color: '#7dd3fc' }}>Login</Link>
      </div>
      <pre style={{ marginTop: 20 }}>{JSON.stringify(stats, null, 2)}</pre>
    </main>
  )
}

import { NextResponse } from 'next/server'
export async function POST(req){
  const cookie = req.headers.get('cookie') || ''
  const match = cookie.match(/(?:^|; )ai_token=([^;]+)/)
  const token = match ? match[1] : null
  if(!token) return new NextResponse('Unauthorized', { status: 401 })
  // validate token via agent-core
  const validate = await fetch((process.env.NEXT_PUBLIC_AGENT_CORE_URL || 'http://localhost:8001') + '/auth/validate', { headers: { Authorization: 'Bearer ' + token } })
  if(!validate.ok) return new NextResponse('Invalid token', { status: 401 })
  const body = await req.json()
  const target = body.target || '/invoke_tool'
  const res = await fetch((process.env.NEXT_PUBLIC_AGENT_CORE_URL || 'http://localhost:8001') + target, { method: 'POST', headers: { Authorization: 'Bearer ' + token, 'Content-Type': 'application/json' }, body: JSON.stringify(body.payload || {}) })
  const j = await res.json()
  return NextResponse.json(j)
}

import { NextResponse } from 'next/server'
export async function POST(req){
  // read cookie from request headers (Next forwards cookies automatically to route)
  const cookie = req.headers.get('cookie') || ''
  // extract ai_refresh cookie
  const match = cookie.match(/(?:^|; )ai_refresh=([^;]+)/)
  const token = match ? match[1] : null
  if(!token) return new NextResponse('No refresh token', { status: 401 })
  // call agent-core refresh endpoint with token in Authorization header for simplicity
  const res = await fetch(process.env.NEXT_PUBLIC_AGENT_CORE_URL || 'http://localhost:8001/auth/refresh', { method:'POST', headers: { 'Authorization': token } })
  if(!res.ok) return new NextResponse('Refresh failed', { status: 401 })
  const j = await res.json()
  const access = j.get('access_token') || j.access_token || null
  if(!access) return new NextResponse('No access token', { status: 500 })
  const response = NextResponse.json({ok:true})
  response.cookies.set('ai_token', access, { httpOnly: true, path: '/', sameSite: 'lax', secure: process.env.NODE_ENV === 'production' })
  return response
}

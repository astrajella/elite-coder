import { NextResponse } from 'next/server'

export async function POST(req) {
  const body = await req.json()
  // forward login to agent-core
  const res = await fetch(process.env.NEXT_PUBLIC_AGENT_CORE_URL || 'http://localhost:8001/auth/login', {
    method: 'POST',
    body: new URLSearchParams(body)
  })

  if (!res.ok) {
    return new NextResponse('Unauthorized', { status: 401 })
  }

  const j = await res.json()
  const access = j.access_token
  const refresh = j.refresh_token
  const refresh_expires = j.refresh_expires
  const response = NextResponse.json({ ok: true })

  // set httpOnly cookies
  response.cookies.set('ai_token', access, {
    httpOnly: true,
    path: '/',
    sameSite: 'Strict',
    secure: process.env.NODE_ENV === 'production',
    maxAge: 3600
  })

  if (refresh) {
    response.cookies.set('ai_refresh', refresh, {
      httpOnly: true,
      path: '/',
      sameSite: 'Strict',
      secure: process.env.NODE_ENV === 'production',
      maxAge: 604800
    })
  }

  return response
}

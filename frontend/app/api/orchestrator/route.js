import { NextResponse } from 'next/server'

export async function POST(req) {
  const body = await req.json()
  const url = (process.env.NEXT_PUBLIC_ORCH_URL || 'http://localhost:8010') + '/orchestrate'
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  })
  const j = await res.json()
  return NextResponse.json(j)
}

import { NextResponse } from 'next/server'
export async function GET(req){
  // proxy stream URL with redirect
  const url = (process.env.NEXT_PUBLIC_ORCH_URL || 'http://localhost:8010') + req.nextUrl.pathname.replace('/api/orchestrator','');
  return NextResponse.redirect(url);
}

import { NextResponse } from 'next/server'
export async function GET(req, { params }){
  const run_id = params.run_id;
  const orch = process.env.NEXT_PUBLIC_ORCH_URL || 'http://localhost:8010';
  const url = orch + '/runs/' + encodeURIComponent(run_id) + '/export_csv';
  const res = await fetch(url, { method: 'GET' });
  const blob = await res.arrayBuffer();
  return new NextResponse(blob, { status: res.status, headers: { 'Content-Type': 'text/csv', 'Content-Disposition': res.headers.get('Content-Disposition') || '' } });
}

import { cookies } from 'next/headers'
import { redirect } from 'next/navigation'

import {useEffect, useState} from 'react'
const cookieStore = cookies();
const token = cookieStore.get('ai_token');
if(!token){
  // attempt refresh
  try{
    const base = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:3000'
    const resp = await fetch(base + '/api/auth/refresh', { method: 'POST', cache: 'no-store', headers: { cookie: cookieStore.get('ai_refresh') ? ('ai_refresh=' + cookieStore.get('ai_refresh').value) : '' } })
    if(!resp.ok){ redirect('/login') }
  }catch(e){ redirect('/login') }
}

export default function Artifacts(){ const [arts,setArts]=useState([]); useEffect(()=>{ fetch('/api/agent/artifacts').then(r=>r.json()).then(j=>setArts(j.artifacts||[])).catch(()=>{}) },[]); return (<div style={{padding:20, background:'#071025', color:'#e6eef8'}}><h1>Artifacts</h1><ul>{arts.map(a=> <li key={a.name}><a href={'/api/agent/artifacts/download?name='+encodeURIComponent(a.path)}>{a.name}</a></li>)}</ul></div>) }

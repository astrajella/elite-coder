import { cookies } from 'next/headers'
import { redirect } from 'next/navigation'

'use client';
import dynamic from 'next/dynamic'
import {useState} from 'react'
const Editor = dynamic(()=>import('react-monaco-editor'), {ssr:false})
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

export default function Monaco(){ const [modified,setModified]=useState('def add(a,b):\n  return a+b\n'); async function commit(){ const res = await fetch('/api/agent/commit',{method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({commit_message:'Edit', patches:[{path:'src/math.py', type:'replace', content:modified}]})}); const j=await res.json(); alert(JSON.stringify(j)); } return (<div style={{padding:20, background:'#071025', color:'#e6eef8'}}><h1>Monaco (App Router)</h1><Editor width='100%' height={400} language='python' value={modified} onChange={v=>setModified(v)}/><div><button onClick={commit}>Commit</button></div></div>) }

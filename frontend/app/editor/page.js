import { cookies } from 'next/headers'
import { redirect } from 'next/navigation'

'use client';
import {useState, useRef} from 'react';
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

export default function Editor(){ const [prompt,setPrompt]=useState('Write a small Python function'); const [out,setOut]=useState(''); async function run(){ const res = await fetch('/api/agent/invoke_tool', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({tool:'generate_code', payload:{prompt}, persona:'coder'})}); const j=await res.json(); setOut(JSON.stringify(j,null,2)); } return (<div style={{padding:20, background:'#071025', color:'#e6eef8'}}><h1>Editor (App Router)</h1><textarea value={prompt} onChange={e=>setPrompt(e.target.value)} style={{width:'100%',height:160}}></textarea><div><button onClick={run} style={{padding:8, background:'#10b981'}}>Run</button></div><pre>{out}</pre></div>) }

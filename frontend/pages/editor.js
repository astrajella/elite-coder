import React, {useState, useEffect, useRef} from 'react'

export default function Editor(){
  const [prompt, setPrompt] = useState('Write a small Python function that adds two numbers.')
  const [out, setOut] = useState('')
  const [streaming, setStreaming] = useState(false)
  const evRef = useRef(null)

  async function runOnce(){
    const token = (typeof window !== 'undefined' && localStorage.getItem('ai_token')) || process.env.NEXT_PUBLIC_DEV_TOKEN || null
    const res = await fetch('/api/agent/invoke_tool', {method:'POST', headers:{'Content-Type':'application/json','Authorization':'Bearer '+token}, body: JSON.stringify({tool:'generate_code', payload:{prompt}, persona:'coder'})})
    const j = await res.json()
    setOut(JSON.stringify(j,null,2))
  }

  function startStream(provider='openrouter'){
    setOut(''); setStreaming(true)
    const token = (typeof window !== 'undefined' && localStorage.getItem('ai_token')) || process.env.NEXT_PUBLIC_DEV_TOKEN || null
    const url = `/api/agent/stream?provider=${provider}&prompt=` + encodeURIComponent(prompt)
    const es = new EventSource(url, { withCredentials: false })
    evRef.current = es
    es.onmessage = (e) => {
      try {
        const d = JSON.parse(e.data)
        setOut(prev => prev + d.chunk)
      } catch(err){}
    }
    es.onerror = (e) => { setStreaming(false); es.close(); }
  }

  function stopStream(){
    if(evRef.current){ evRef.current.close(); setStreaming(false); }
  }

  return (<div style={{background:'#071025', color:'#e6eef8', minHeight:'100vh', padding:20}}>
    <h1>Editor (streaming)</h1>
    <textarea value={prompt} onChange={e=>setPrompt(e.target.value)} style={{width:'100%',height:160}}></textarea>
    <div style={{marginTop:10, display:'flex', gap:10}}>
      <button onClick={()=>startStream('openrouter')} style={{padding:'8px 12px', background:'#2563eb', borderRadius:6}}>Stream (OpenRouter)</button>
      <button onClick={()=>startStream('openai')} style={{padding:'8px 12px', background:'#0ea5a5', borderRadius:6}}>Stream (OpenAI)</button>
      <button onClick={()=>startStream('anthropic')} style={{padding:'8px 12px', background:'#7c3aed', borderRadius:6}}>Stream (Anthropic)</button>
      <button onClick={stopStream} style={{padding:'8px 12px', background:'#ef4444', borderRadius:6}}>Stop</button>
      <button onClick={runOnce} style={{padding:'8px 12px', background:'#10b981', borderRadius:6}}>Run Once</button>
    </div>
    <pre style={{marginTop:20, whiteSpace:'pre-wrap'}}>{out}</pre>
  </div>)
}

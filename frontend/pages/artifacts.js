import React, {useEffect, useState} from 'react'

export default function Artifacts(){
  const [arts, setArts] = useState([])
  useEffect(()=>{
    fetch('/api/agent/artifacts').then(r=>r.json()).then(j=>setArts(j.artifacts||[])).catch(()=>{})
  },[])
  return (<div style={{padding:20, background:'#071025', color:'#e6eef8', minHeight:'100vh'}}>
    <h1>Artifacts</h1>
    <ul>
      {arts.map(a=> <li key={a.name}><a href={'/api/agent/artifacts/download?name='+encodeURIComponent(a.path)} style={{color:'#7dd3fc'}}>{a.name}</a></li>)}
    </ul>
  </div>)
}

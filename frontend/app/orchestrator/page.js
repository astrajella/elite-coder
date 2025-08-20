'use client';
import { useState, useEffect, useRef } from 'react';
import dynamic from 'next/dynamic';
// Recharts will be dynamically imported to avoid SSR issues if not installed.
const Recharts = {
  BarChart: null, Bar, XAxis: null, YAxis: null, Tooltip: null, ResponsiveContainer: null, PieChart: null, Pie: null, Cell: null, Legend: null
};
let rechartsImported = false;
async function loadRecharts(){
  if(rechartsImported) return;
  try{
    const R = await import('recharts');
    Recharts.BarChart = R.BarChart;
    Recharts.Bar = R.Bar;
    Recharts.XAxis = R.XAxis;
    Recharts.YAxis = R.YAxis;
    Recharts.Tooltip = R.Tooltip;
    Recharts.ResponsiveContainer = R.ResponsiveContainer;
    Recharts.PieChart = R.PieChart;
    Recharts.Pie = R.Pie;
    Recharts.Cell = R.Cell;
    Recharts.Legend = R.Legend;
    rechartsImported = true;
  }catch(e){
    console.warn('Recharts not installed. Install with `npm install recharts` to enable charts.', e);
  }
}

export default function OrchestratorPage(){
  const [planText, setPlanText] = useState(JSON.stringify({plan_id:'demo', steps:[{step_id:'s1', description:'summarize', persona:'summarizer', tool:'summarize_tokens', payload:{context_blocks:['example']},},{step_id:'s2', description:'generate code', persona:'coder', tool:'generate_code', payload:{step_id:'s2', files_requested:[]}}]}, null, 2));
  const [runId, setRunId] = useState(null);
  const [runData, setRunData] = useState(null);
  const [chartsOk, setChartsOk] = useState(false);
  const evtRef = useRef(null);

  useEffect(()=>{ loadRecharts().then(()=>setChartsOk(rechartsImported)); },[]);

  async function startRun(){
    try{
      const body = { plan: JSON.parse(planText) };
      const res = await fetch('/api/orchestrator/orchestrate', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
      const j = await res.json();
      setRunId(j.run_id);
      listenRun(j.run_id);
    }catch(e){ alert('start error ' + e.message) }
  }

  function listenRun(id){
    if(evtRef.current){ evtRef.current.close() }
    const url = '/api/orchestrator/runs/stream/' + id;
    const es = new EventSource(url);
    evtRef.current = es;
    es.onmessage = (e) => {
      try{ const d = JSON.parse(e.data); setRunData(d); }catch(err){}
    }
    es.onerror = ()=>{ es.close(); }
  }

  // Derive chart data from runData
  function getStepTimingData(){
    if(!runData || !runData.trace) return [];
    const steps = runData.trace.steps || [];
    return steps.map((s, idx)=>{
      const dur = (s.result && s.result.duration) ? Number(s.result.duration) : (s.ended_at && s.started_at ? (s.ended_at - s.started_at) : 0);
      return { name: s.description || s.step_id || ('step'+idx), duration: Math.round((dur||0)*1000) }; // ms
    });
  }

  function getPersonaCostData(){
    if(!runData || !runData.trace) return [];
    const steps = runData.trace.steps || [];
    const map = {};
    steps.forEach(s=>{
      const persona = s.persona || (s.result && s.result.response && s.result.response.persona) || 'unknown';
      const cost = (s.result && s.result.response && (s.result.response.cost || s.result.response.cost_est)) || (s.result && s.result.response && s.result.response.token_est ? (Number(s.result.response.token_est)*0.000002) : 0);
      map[persona] = (map[persona] || 0) + Number(cost || 0);
    });
    return Object.keys(map).map(k=>({ name:k, value: Number(map[k].toFixed(8)) }));
  }

  const stepTimingData = getStepTimingData();
  const personaCostData = getPersonaCostData();

  return (<div style={{padding:20, background:'#071025', color:'#e6eef8', minHeight:'100vh'}}>
    <h1>Orchestrator Playground — Visuals</h1>
    <div style={{display:'flex', gap:12}}>
      <textarea value={planText} onChange={e=>setPlanText(e.target.value)} style={{width:520, height:320}} />
      <div style={{flex:1}}>
        <div style={{display:'flex', gap:8}}>
          <button onClick={startRun} style={{padding:8, background:'#10b981'}}>Run Plan</button>
          <button onClick={()=>{ if(evtRef.current) evtRef.current.close(); setRunId(null); setRunData(null); }}>Clear</button>
        </div>
        <div style={{marginTop:12}}><strong>Run ID:</strong> {runId}</div><div style={{marginTop:12}}>
  <button onClick={async ()=>{ if(!runId){ alert('No run'); return; } const res = await fetch('/api/orchestrator/export/' + runId); if(res.ok){ const blob = await res.blob(); const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = `run_${runId}_metrics.csv`; document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url); } else { alert('Export failed'); } }} style={{marginLeft:12, padding:8, background:'#3b82f6'}}>Download CSV</button>
</div>

        <div style={{marginTop:12}}><strong>State:</strong> {runData ? runData.state : 'n/a'}</div>
      </div>
    </div>

    <div style={{marginTop:20, display:'grid', gridTemplateColumns: '1fr 400px', gap:20}}>
      <div style={{background:'#041226', padding:12, borderRadius:8}}>
        <h3>Per-step timing (ms)</h3>
        {chartsOk && Recharts.ResponsiveContainer ? (
          <Recharts.ResponsiveContainer width='100%' height={240}>
            <Recharts.BarChart data={stepTimingData}>
              <Recharts.XAxis dataKey='name' stroke='#9ca3af' />
              <Recharts.YAxis stroke='#9ca3af' />
              <Recharts.Tooltip />
              <Recharts.Bar dataKey='duration' fill='#06b6d4' />
            </Recharts.BarChart>
          </Recharts.ResponsiveContainer>
        ) : (
          <div style={{padding:12}}>
            <div style={{color:'#9ca3af'}}>Recharts not installed. Run <code>npm install recharts</code> in the frontend to enable charts.</div>
            <pre style={{marginTop:8}}>{JSON.stringify(stepTimingData, null, 2)}</pre>
          </div>
        )}
      </div>

      <div style={{background:'#041226', padding:12, borderRadius:8}}>
        <h3>Per-persona cost breakdown</h3>
        {chartsOk && Recharts.PieChart ? (
          <Recharts.ResponsiveContainer width='100%' height={240}>
            <Recharts.PieChart>
              <Recharts.Pie data={personaCostData} dataKey='value' nameKey='name' cx='50%' cy='50%' outerRadius={80} label>
                {personaCostData.map((entry, index)=>(
                  <Recharts.Cell key={`cell-${index}`} fill={['#06b6d4','#10b981','#f59e0b','#ef4444'][index % 4]} />
                ))}
              </Recharts.Pie>
              <Recharts.Tooltip />
              <Recharts.Legend />
            </Recharts.PieChart>
          </Recharts.ResponsiveContainer>
        ) : (
          <div style={{padding:12}}>
            <div style={{color:'#9ca3af'}}>Recharts not installed. Run <code>npm install recharts</code> in the frontend to enable charts.</div>
            <pre style={{marginTop:8}}>{JSON.stringify(personaCostData, null, 2)}</pre>
          </div>
        )}
      </div>
    </div>

    <div style={{marginTop:20, background:'#031021', padding:12, borderRadius:8}}>
      <h3>Run Trace</h3>
      <pre style={{whiteSpace:'pre-wrap'}}>{JSON.stringify(runData, null, 2)}</pre>
    </div>
  </div>)
}

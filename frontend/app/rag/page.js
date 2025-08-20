'use client';
import { useState } from 'react';

export default function RagDemo(){
  const [query, setQuery] = useState('');
  const [topK, setTopK] = useState(3);
  const [hops, setHops] = useState(1);
  const [expansionK, setExpansionK] = useState(2);
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function runSearch(e){
    e && e.preventDefault();
    setLoading(true); setError(null); setResults(null);
    try {
      const base = process.env.NEXT_PUBLIC_RETRIEVAL_URL || (process.env.NEXT_PUBLIC_API_BASE || '') + '/api/retrieval/search';
      // If NEXT_PUBLIC_RETRIEVAL_URL not set, try relative proxy path
      const url = base || '/api/retrieval/search';
      const res = await fetch(url, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ query, top_k: Number(topK), hops: Number(hops), expansion_k: Number(expansionK) })
      });
      if(!res.ok){
        const txt = await res.text();
        throw new Error('Status ' + res.status + ': ' + txt);
      }
      const j = await res.json();
      setResults(j);
    } catch(err){
      setError(err.message || String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{padding:20, background:'#071025', color:'#e6eef8', minHeight:'100vh'}}>
      <h1>RAG Demo</h1>
      <form onSubmit={runSearch} style={{display:'grid', gap:8, maxWidth:900}}>
        <label>Query</label>
        <input value={query} onChange={e=>setQuery(e.target.value)} style={{padding:8, fontSize:16}} placeholder="Ask something about the project..." />
        <div style={{display:'flex', gap:8}}>
          <div><label>Top K</label><input type="number" value={topK} onChange={e=>setTopK(e.target.value)} style={{width:80}}/></div>
          <div><label>Hops</label><input type="number" value={hops} onChange={e=>setHops(e.target.value)} style={{width:80}}/></div>
          <div><label>Expansion K</label><input type="number" value={expansionK} onChange={e=>setExpansionK(e.target.value)} style={{width:80}}/></div>
        </div>
        <div>
          <button type="submit" style={{padding:8, background:'#06b6d4', borderRadius:6}} disabled={loading}>{loading ? 'Searching...' : 'Search'}</button>
          <button type="button" style={{padding:8, marginLeft:8}} onClick={_=>{ setQuery(''); setResults(null); setError(null); }}>Clear</button>
        </div>
      </form>

      <div style={{marginTop:20}}>
        {error && <div style={{color:'#f87171'}}>Error: {error}</div>}
        {results && (
          <div>
            <h3>Results (hops_used: {results.hops_used ?? 'n/a'})</h3>
            <ol>
              {(results.retrieved || []).map((r, idx) => (
                <li key={r.id} style={{marginBottom:12, padding:10, background:'#081a2b', borderRadius:6}}>
                  <div style={{fontSize:12, color:'#9ca3af'}}>id: {r.id} — score: {Number(r.score).toFixed(4)}</div>
                  <pre style={{whiteSpace:'pre-wrap', marginTop:6}}>{r.text}</pre>
                </li>
              ))}
            </ol>
            <pre style={{marginTop:10, background:'#031021', padding:10}}>{JSON.stringify(results, null, 2)}</pre>
          </div>
        )}
      </div>
    </div>
  )
}

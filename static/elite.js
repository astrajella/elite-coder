function showError(msg){
  const el = document.getElementById('globalError');
  if(el){ el.textContent = msg; el.classList.remove('hidden'); setTimeout(()=>el.classList.add('hidden'), 5000); }
}
async function api(path, method='GET', data=null){
  const opt = { method, headers: {'Content-Type':'application/json'} };
  if(data) opt.body = JSON.stringify(data);
  const res = await fetch(path, opt);
  return await res.json();
}
const logEl = document.getElementById('log');
function log(x){
  const s = (typeof x === 'string') ? x : JSON.stringify(x,null,2);
  logEl.textContent += s + "\n";
  logEl.scrollTop = logEl.scrollHeight;
}

// Theme
document.getElementById('themeBtn').addEventListener('click', ()=> document.documentElement.classList.toggle('dark'));

// Tabs
document.querySelectorAll('.tab').forEach(btn=>{
  btn.addEventListener('click', ()=>{
    document.querySelectorAll('.tab').forEach(b=>b.classList.remove('ring','ring-emerald-500'));
    btn.classList.add('ring','ring-emerald-500');
  });
});

// Monaco
let editor;
require.config({ paths: { 'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.45.0/min/vs' } });
require(['vs/editor/editor.main'], function(){
  editor = monaco.editor.create(document.getElementById('editor'), {
    value: '// Prepare a CodePatchList here if you want to apply it via /api/apply_patches\n',
    language: 'json',
    theme: 'vs-dark',
    automaticLayout: true,
    minimap: { enabled: false },
    fontSize: 13
  });
});

// Keyboard shortcuts
window.addEventListener('keydown', (e)=>{
  if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
    runPipeline();
    e.preventDefault();
  }
});

// Models + artifacts + history
async function refreshModels(){
  const m = await api('/api/models');
  document.getElementById('modelBadge').textContent = `coder: ${m.coder} • critic: ${m.critic} • summarizer: ${m.summarizer}`;
  const modelsDiv = document.getElementById('personaModels');
  modelsDiv.innerHTML = '';
  ['coder','critic','summarizer'].forEach(k=>{
    const div = document.createElement('div');
    div.className='px-2 py-1 rounded bg-zinc-800 border border-zinc-700';
    div.textContent=`${k}: ${m[k]}`;
    modelsDiv.appendChild(div);
  });
}
async function refreshArtifacts(){
  const list = await api('/api/artifacts');
  const ul = document.getElementById('artifacts'); ul.innerHTML='';
  list.forEach(a=>{
    const li = document.createElement('li');
    const aEl = document.createElement('a');
    aEl.href = 'sandbox:' + a.path;
    aEl.textContent = `${a.name} (${(a.size/1024).toFixed(1)} KB)`;
    aEl.className='hover:underline';
    li.appendChild(aEl);
    ul.appendChild(li);
  });
}
async function refreshHistory(){
  const list = await api('/api/history');
  const ul = document.getElementById('history'); ul.innerHTML='';
  list.slice().reverse().forEach(h=>{
    const li = document.createElement('li');
    li.className='px-2 py-1 rounded bg-zinc-800 border border-zinc-700';
    const d = new Date(h.ts*1000).toLocaleString();
    const a = document.createElement('a');
    a.href = 'sandbox:' + h.artifact;
    a.textContent = `${d} • ${h.commit_id} • ${(h.size/1024).toFixed(1)} KB`;
    li.appendChild(a);
    ul.appendChild(li);
  });
}
refreshModels(); refreshArtifacts(); refreshHistory();

// RAG Explorer
document.getElementById('ragSearch').addEventListener('click', async ()=>{
  const q = document.getElementById('ragQuery').value;
  const res = await api('/api/rag/search', 'POST', {q, k:5});
  const ul = document.getElementById('ragResults'); ul.innerHTML='';
  res.forEach(r=>{
    const li = document.createElement('li');
    li.className='p-2 rounded bg-zinc-800/60 border border-zinc-700';
    li.textContent = r.text.slice(0,220) + '…';
    ul.appendChild(li);
  });
});

// Buttons
document.getElementById('planBtn').addEventListener('click', runPlanOnly);
document.getElementById('runBtn').addEventListener('click', runPipeline);
document.getElementById('streamBtn').addEventListener('click', runStream);
document.getElementById('clearLog').addEventListener('click', ()=> logEl.textContent='');

async function runPlanOnly(){
  const goal = document.getElementById('goal').value;
  const topk = parseInt(document.getElementById('topk').value||3,10);
  const r = await api('/tool_retrieve_rag','POST',{query:goal, top_k:topk});
  const s = await api('/tool_summarize_tokens','POST',{context_blocks:(r.retrieved||[]).map(x=>x.text), max_tokens:800});
  const p = await api('/tool_plan_step','POST',{goal, constraints:{}, current_files:[]});
  document.getElementById('pipeline').textContent = JSON.stringify({retrieve:r,summarize:s,plan:p}, null, 2);
  document.getElementById('costBadge').textContent = `tokens: ${s.tokens_est} • $${s.cost_estimate.toFixed(3)}`;
}

async function runPipeline(){
  const runBtn = document.getElementById('runBtn'); if(runBtn){runBtn.disabled=true; runBtn.textContent='Running...';}
  try{
  const runBtn = document.getElementById('runBtn'); if(runBtn){ runBtn.disabled=true; runBtn.textContent='Running...'; }
  const goal = document.getElementById('goal').value;
  const topk = parseInt(document.getElementById('topk').value||3,10);
  log('→ retrieve');
  const r = await api('/tool_retrieve_rag','POST',{query:goal, top_k:topk}); log(r);
  log('→ summarize');
  const s = await api('/tool_summarize_tokens','POST',{context_blocks:(r.retrieved||[]).map(x=>x.text), max_tokens:800}); log(s);
  document.getElementById('costBadge').textContent = `tokens: ${s.tokens_est} • $${s.cost_estimate.toFixed(3)}`;
  log('→ plan');
  const p = await api('/tool_plan_step','POST',{goal, constraints:{}, current_files:[]}); log(p);
  log('→ code');
  const g = await api('/tool_generate_code','POST',{plan_id:p.plan_id, step_id:'code', files_requested:[
    {path:'docs/DEV_NOTES.md', file_schema:'markdown'},
    {path:'static/agent_output.js', file_schema:'javascript'}
  ], context_summary:s.summary, style_guides:['docstrings'], tests_to_pass:['tests/test_api.py']}); log(g);
  document.getElementById('diff').textContent = JSON.stringify(g, null, 2);
  log('→ validate');
  const v = await api('/tool_validate_schema','POST',{schema_name:'CodePatchList', payload:g}); log(v);
  log('→ tests & lint');
  const t = await api('/tool_run_tests','POST',{test_selector:'all', timeout_sec:45}); log(t);
  log('→ critic');
  const c = await api('/tool_critic_review','POST',{patches:g.patches, test_results:t, plan:p}); log(c);
  log('→ commit');
  const commit = await api('/tool_commit_and_artifact','POST',{plan_id:p.plan_id, step_id:'finalize', patches:g.patches, commit_message:'agent commit', artifact_targets:['zip']}); log(commit);
  refreshArtifacts(); refreshHistory();
  document.getElementById('pipeline').textContent = JSON.stringify({p,r,s,g,v,t,c,commit}, null, 2);
}

function runStream(){
  const goal = encodeURIComponent(document.getElementById('goal').value);
  const topk = encodeURIComponent(document.getElementById('topk').value||3);
  const ev = new EventSource(`/sse/run?goal=${goal}&top_k=${topk}`);
  ev.addEventListener('status', (e)=> log(JSON.parse(e.data)));
  ev.addEventListener('retrieve', (e)=> log(JSON.parse(e.data)));
  ev.addEventListener('summarize', (e)=> {
    const d = JSON.parse(e.data);
    document.getElementById('costBadge').textContent = `tokens: ${d.tokens_est} • $${d.cost_estimate.toFixed(3)}`;
    log(d);
  });
  ev.addEventListener('plan', (e)=> log(JSON.parse(e.data)));
  ev.addEventListener('code', (e)=> {
    const d = JSON.parse(e.data);
    document.getElementById('diff').textContent = JSON.stringify(d, null, 2);
    log(d);
  });
  ev.addEventListener('validate', (e)=> log(JSON.parse(e.data)));
  ev.addEventListener('tests', (e)=> log(JSON.parse(e.data)));
  ev.addEventListener('error', ()=> ev.close());
}

// === LEDGER ANALYTICS ADDON ===
(function() {
  const hasReact = !!window.React && !!window.ReactDOM && !!window.Recharts;
  if (!hasReact) return;

  const e = React.createElement;
  const { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, LineChart, Line, PieChart, Pie, Cell } = window.Recharts;

  function DownloadButton({ path, filename, label }) {
    const onClick = async () => {
      const res = await fetch(path);
      const text = await res.text();
      const blob = new Blob([text], { type: path.endsWith('.csv') ? 'text/csv' : 'text/plain' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = filename; a.click();
      URL.revokeObjectURL(url);
    };
    return e('button', { className: 'px-3 py-1 bg-emerald-600 rounded hover:bg-emerald-500', onClick }, label);
  }

  function PersonaCards({ stats }) {
    const entries = Object.entries(stats || {});
    return e('div', { className: 'grid grid-cols-1 md:grid-cols-3 gap-4' },
      entries.map(([persona, s]) =>
        e('div', { key: persona, className: 'p-3 rounded bg-gray-800 border border-gray-700' },
          e('div', { className: 'text-sm text-gray-400' }, persona),
          e('div', { className: 'mt-2 text-xs text-gray-400' }, 'Runs: ' + (s.total_runs||0)),
          e('div', { className: 'mt-1 text-xs text-gray-400' }, 'Tokens: ' + (s.total_tokens||0)),
          e('div', { className: 'mt-1 text-xs text-gray-400' }, 'Cost: $' + (s.total_cost||0).toFixed(4)),
          e('div', { className: 'mt-1 text-xs text-gray-400' }, 'Avg ms: ' + Math.round((s.avg_duration||0)*1000))
        )
      )
    );
  }

  function DailyBars({ data, dataKey, title }) {
    return e('div', { className: 'p-3 rounded bg-gray-800 border border-gray-700' },
      e('div', { className: 'text-sm mb-2 text-gray-300' }, title),
      e(ResponsiveContainer, { width: '100%', height: 240 },
        e(BarChart, { data },
          e(CartesianGrid, { strokeDasharray: '3 3' }),
          e(XAxis, { dataKey: 'date' }),
          e(YAxis, null),
          e(Tooltip, null),
          e(Legend, null),
          e(Bar, { dataKey, name: dataKey.replace('total_', '').toUpperCase() })
        )
      )
    );
  }

  function AnalyticsApp() {
    const [stats, setStats] = React.useState({ persona: {}, tool: {}, totals: { runs:0, tokens:0, cost:0 } });
    const [daily, setDaily] = React.useState([]);

    React.useEffect(() => {
      // Initial fetch
      fetch('/ledger/stats').then(r=>r.json()).then(setStats).catch(()=>{});
      fetch('/ledger/daily').then(r=>r.json()).then(j=>setDaily(j.daily||[])).catch(()=>{});
      // SSE updates
      try {
        const evt = new EventSource('/ledger/stream');
        evt.onmessage = (ev) => {
          try {
            const data = JSON.parse(ev.data);
            setStats(data);
            // also refresh daily lazily
            fetch('/ledger/daily').then(r=>r.json()).then(j=>setDaily(j.daily||[])).catch(()=>{});
          } catch(e){}
        };
      } catch(e) {}
    }, []);

    return e('div', { className: 'space-y-3' },
      e('div', { id: 'exportButtons', className: 'flex gap-2' },
        e(DownloadButton, { path: '/ledger/runs/export', filename: 'runs.csv', label: 'Export Runs CSV' }),
        e(DownloadButton, { path: '/ledger/daily/export', filename: 'daily.csv', label: 'Export Daily CSV' })
      ),
      e(PersonaCards, { stats: stats.persona || {} }),
      e('div', { id: 'dailyCharts', className: 'grid grid-cols-1 md:grid-cols-2 gap-4' },
        e(DailyBars, { data: daily, dataKey: 'total_cost', title: 'Daily Cost' }),
        e(DailyBars, { data: daily, dataKey: 'total_tokens', title: 'Daily Tokens' }),
      )
    );
  }

  function mountAnalytics() {
    const mount = document.getElementById('analyticsPanel');
    if (!mount) return;
    const root = ReactDOM.createRoot(mount);
    root.render(e(AnalyticsApp));
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mountAnalytics);
  } else {
    mountAnalytics();
  }
})();

// auto-inserted finally for runPipeline
async function __resetRunBtn(){ const runBtn=document.getElementById('runBtn'); if(runBtn){runBtn.disabled=false; runBtn.textContent='Run ⏵';} }
// --- UX helpers ---
function showToast(msg){
  const box = document.getElementById('toast') || (function(){
    const d=document.createElement('div'); d.id='toast';
    d.style.position='fixed'; d.style.bottom='16px'; d.style.right='16px';
    d.style.padding='10px 14px'; d.style.background='#111827'; d.style.color='#fff';
    d.style.borderRadius='8px'; d.style.boxShadow='0 8px 30px rgba(0,0,0,.25)'; d.style.zIndex='9999';
    document.body.appendChild(d); return d;
  })();
  box.textContent = msg; box.style.opacity='1';
  setTimeout(()=>{ box.style.opacity='0'; }, 3500);
}
async function guardedFetch(url, opts){
  const res = await fetch(url, opts||{});
  if(!res.ok){
    const t = await res.text();
    showToast('Error '+res.status+': '+t);
    throw new Error(t);
  }
  return res;
}


function _showToast(msg){
  const el = document.getElementById('toast');
  if(!el){ console.log('TOAST:', msg); return; }
  el.textContent = msg; el.style.display = 'block';
  setTimeout(()=>{ el.style.display='none'; }, 3500);
}

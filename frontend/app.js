
(function(){
  const e = React.createElement;
  const {BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer} = Recharts;

  const API = window.ORCH_API || (location.origin);

  const traceBase = (window.TRACE_BASE || localStorage.getItem('TRACE_BASE') || '');

  async function fetchJSON(url){
    const r = await fetch(url, {headers: {'X-API-Key': localStorage.getItem('API_KEY') || ''}});
    if(!r.ok) throw new Error(await r.text());
    return r.json();
  }
  async function fetchText(url){
    const r = await fetch(url, {headers: {'X-API-Key': localStorage.getItem('API_KEY') || ''}});
    if(!r.ok) throw new Error(await r.text());
    return r.text();
  }

  function renderSteps(rows){
    const el = document.getElementById('stepsTable');
    if(!rows || !rows.length){ el.innerHTML = '<div class="opacity-60">No steps</div>'; return; }
    const header = '<tr class="text-left text-sm opacity-80"><th class="p-2">Step ID</th><th class="p-2">Status</th><th class="p-2">Attempts</th><th class="p-2">Updated</th><th class="p-2">Trace</th></tr>';
    const tr = rows.map(r=>{
      const t = r.trace_id ? r.trace_id : '';
      const link = (traceBase && t) ? `<a target="_blank" href="${traceBase}${t}">${t.slice(0,8)}…</a>` : (t || '-');
      return `<tr class="border-t border-gray-800 text-sm">
        <td class="p-2 font-mono">${r.step_id}</td>
        <td class="p-2">${r.status}</td>
        <td class="p-2">${r.attempts}</td>
        <td class="p-2">${new Date((r.updated_at||0)*1000).toLocaleString()}</td>
        <td class="p-2 font-mono">${link}</td>
      </tr>`
    }).join('');
    el.innerHTML = `<table class="w-full">${header}${tr}</table>`;
  }

  function parseHistogram(metricsText, metricName){
    // Prometheus exposition format: metricName_bucket{le="0.1"} 3
    const lines = metricsText.split(/\n/);
    const rows = [];
    for(const ln of lines){
      if(!ln.startsWith(metricName+"_bucket")) continue;
      const m = ln.match(/le="([^"]+)"\}\s+(\d+)/);
      if(m){
        rows.push({le: parseFloat(m[1]), count: parseInt(m[2],10)});
      }
    }
    // Compute per-bucket increments (cumulative to delta)
    rows.sort((a,b)=>a.le-b.le);
    let prev = 0;
    const out = rows.map(r=>{
      const delta = r.count - prev; prev = r.count;
      return {bucket: r.le, value: Math.max(delta,0)};
    });
    return out;
  }

  async function refreshCharts(){
    try{
      const txt = await fetchText(API + '/metrics');
      const d1 = parseHistogram(txt, 'orch_step_duration_seconds');
      const d2 = parseHistogram(txt, 'orch_lease_wait_seconds');
      renderBar('durationChart', d1);
      renderBar('leaseChart', d2);
    }catch(e){ console.error(e); }
  }

  function renderBar(mountId, data){
    const mount = document.getElementById(mountId);
    ReactDOM.render(
      e(ResponsiveContainer, {width: '100%', height: 260},
        e(BarChart, {data},
          e(CartesianGrid, {strokeDasharray: "3 3"}),
          e(XAxis, {dataKey: "bucket"}),
          e(YAxis, {}),
          e(Tooltip, {}),
          e(Bar, {dataKey: "value"})
        )
      ), mount
    );
  }

  async function loadRun(){
    const runId = document.getElementById('runId').value.trim();
    if(!runId) return;
    const rows = await fetchJSON(API + '/admin/run_steps/' + encodeURIComponent(runId) + '?limit=500');
    renderSteps(rows);
  }

  document.getElementById('loadBtn').addEventListener('click', loadRun);

  // periodic charts refresh
  setInterval(refreshCharts, 3000);
  refreshCharts();
})();


// Quantile parse from Prometheus Summary exposition
function parseQuantiles(metricsText, base){
  // lines like: base{quantile="0.5"} 0.123
  const out = {};
  for(const ln of metricsText.split(/\n/)){
    if(!ln.startsWith(base+'{')) continue;
    const q = (ln.match(/quantile="([^"]+)"/)||[])[1];
    const v = parseFloat(ln.split('} ')[1]);
    if(q) out[q] = v;
  }
  return out;
}

// Lease wait breakdown heatmap-ish: stacked bars by bucket per tool
async function renderLeaseHeat(){
  try{
    const r = await fetch(API + '/admin/metrics/lease_wait_breakdown', {headers: {'X-API-Key': localStorage.API_KEY || ''}});
    if(!r.ok) throw new Error(await r.text());
    const j = await r.json();
    // Prepare data for stacked bars
    const tools = Object.keys(j.counts);
    const buckets = j.buckets.concat(['inf']).map(String);
    const data = tools.map(tool => {
      const row = {tool};
      buckets.forEach(b=> row[b] = (j.counts[tool]&&j.counts[tool][b]) || 0);
      return row;
    });
    const {ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Legend, CartesianGrid} = Recharts;
    const mount = document.getElementById('leaseHeat');
    const bars = buckets.map(b => React.createElement(Bar, {dataKey: b, stackId: "a"}));
    ReactDOM.render(
      React.createElement(ResponsiveContainer, {width:"100%", height:300},
        React.createElement(BarChart, {data},
          React.createElement(CartesianGrid, {strokeDasharray:"3 3"}),
          React.createElement(XAxis, {dataKey:"tool"}),
          React.createElement(YAxis, {}),
          React.createElement(Tooltip, {}),
          React.createElement(Legend, {}),
throw new Error('Auto-replaced placeholder: implement logic here');
        )
      ), mount
    );
  }catch(e){ console.error(e); }
}

// Add CSV export buttons
(function(){
  const host = API;
  const container = document.getElementById('stepsTable');
  const bar = document.createElement('div');
  bar.className = "flex gap-2 mt-2";
  bar.innerHTML = `<a class="px-3 py-2 rounded bg-gray-700 hover:bg-gray-600" href="${host}/admin/export/histograms.csv" target="_blank">Download Histograms CSV</a>
  <button id="dlTimeline" class="px-3 py-2 rounded bg-gray-700 hover:bg-gray-600">Download Timeline CSV (current Run)</button>`;
  setTimeout(()=> container.parentNode.insertBefore(bar, container), 500);
  document.addEventListener('click', (ev)=>{
    if(ev.target && ev.target.id==='dlTimeline'){
      const runId = document.getElementById('runId').value.trim();
      if(!runId) return;
      const a = document.createElement('a');
      a.href = host + '/admin/export/run_timeline/' + encodeURIComponent(runId) + '.csv';
      a.target = "_blank";
      a.click();
    }
  });
})();

async function refreshQuantiles(){
  try{
    const txt = await fetchText(API + '/metrics');
    const qD = parseQuantiles(txt, 'orch_step_duration_seconds_summary');
    const qL = parseQuantiles(txt, 'orch_lease_wait_seconds_summary');
    if(qD['0.5']) document.getElementById('q_d_50').textContent = qD['0.5'].toFixed(3);
    if(qD['0.9']) document.getElementById('q_d_90').textContent = qD['0.9'].toFixed(3);
    if(qL['0.5']) document.getElementById('q_l_50').textContent = qL['0.5'].toFixed(3);
    if(qL['0.9']) document.getElementById('q_l_90').textContent = qL['0.9'].toFixed(3);
  }catch(e){ console.error(e); }
}

// extend periodic refresh
setInterval(refreshQuantiles, 3000);
renderLeaseHeat();
refreshQuantiles();


// Sparkline using durations_series
async function renderDurSpark(){
  try{
    const r = await fetch(API + '/admin/metrics/durations_series', {headers: {'X-API-Key': localStorage.API_KEY || ''}});
    if(!r.ok) throw new Error(await r.text());
    const j = await r.json();
    const pts = j.points || [];
    const {ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid} = Recharts;
    const mount = document.getElementById('durSpark');
    ReactDOM.render(
      React.createElement(ResponsiveContainer, {width:"100%", height:120},
        React.createElement(LineChart, {data: pts},
          React.createElement(CartesianGrid, {strokeDasharray:"3 3"}),
          React.createElement(XAxis, {dataKey:"ts", hide:true}),
          React.createElement(YAxis, {hide:true}),
          React.createElement(Tooltip, {}),
          React.createElement(Line, {type:"monotone", dataKey:"duration", dot:false, isAnimationActive:false})
        )
      ), mount
    );
  }catch(e){ console.error(e); }
}

// Persona heatmap
async function renderLeaseHeatPersona(){
  try{
    const r = await fetch(API + '/admin/metrics/lease_wait_breakdown', {headers: {'X-API-Key': localStorage.API_KEY || ''}});
    if(!r.ok) throw new Error(await r.text());
    const j = await r.json();
    const buckets = j.buckets.concat(['inf']).map(String);
    // Group by persona; input currently grouped by tool->bucket; we fetch CSV for persona split instead
    const csvRes = await fetch(API + '/admin/export/lease_heat.csv', {headers: {'X-API-Key': localStorage.API_KEY || ''}});
    const csvTxt = await csvRes.text();
    const rows = csvTxt.trim().split(/\n/).slice(1).map(l=>{
      const [tool, persona, le, count] = l.split(',');
      return {tool, persona, le, count: Number(count)};
    });
    const byPersona = {};
    for(const r of rows){
      const key = r.persona || 'unknown';
      byPersona[key] = byPersona[key] || {};
      byPersona[key][r.le] = (byPersona[key][r.le] || 0) + r.count;
    }
    const data = Object.keys(byPersona).map(persona => {
      const row = {persona};
      buckets.forEach(b => row[b] = byPersona[persona][String(b)] || 0);
      return row;
    });
    const {ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Legend, CartesianGrid} = Recharts;
    const mount = document.getElementById('leaseHeatPersona');
    const bars = buckets.map(b => React.createElement(Bar, {dataKey: b, stackId: "p"}));
    ReactDOM.render(
      React.createElement(ResponsiveContainer, {width:"100%", height:300},
        React.createElement(BarChart, {data},
          React.createElement(CartesianGrid, {strokeDasharray:"3 3"}),
          React.createElement(XAxis, {dataKey:"persona"}),
          React.createElement(YAxis, {}),
          React.createElement(Tooltip, {}),
          ReactDOM.createElement(Legend, {}),
throw new Error('Auto-replaced placeholder: implement logic here');
        )
      ), mount
    );

    document.addEventListener('click', (ev)=>{
      if(ev.target && ev.target.id === 'dlLeaseHeat'){
        const a = document.createElement('a');
        a.href = API + '/admin/export/lease_heat.csv';
        a.target = "_blank";
        a.click();
      }
    });
  }catch(e){ console.error(e); }
}

// Extend quantiles to include p99
async function refreshQuantilesPlus(){
  try{
    const txt = await fetchText(API + '/metrics');
    const qD = parseQuantiles(txt, 'orch_step_duration_seconds_summary');
    const qL = parseQuantiles(txt, 'orch_lease_wait_seconds_summary');
    if(qD['0.5']) document.getElementById('q_d_50').textContent = qD['0.5'].toFixed(3);
    if(qD['0.9']) document.getElementById('q_d_90').textContent = qD['0.9'].toFixed(3);
    if(qD['0.99']) document.getElementById('q_d_99').textContent = qD['0.99'].toFixed(3);
    if(qL['0.5']) document.getElementById('q_l_50').textContent = qL['0.5'].toFixed(3);
    if(qL['0.9']) document.getElementById('q_l_90').textContent = qL['0.9'].toFixed(3);
  }catch(e){ console.error(e); }
}

// Hook into existing intervals
setInterval(refreshQuantilesPlus, 3000);
renderDurSpark();
renderLeaseHeatPersona();
refreshQuantilesPlus();


// ---- Trace Drawer ----
function openTraceDrawer(){ document.getElementById('traceDrawer').classList.remove('hidden'); }
function closeTraceDrawer(){ document.getElementById('traceDrawer').classList.add('hidden'); }
document.addEventListener('click', (ev)=>{
  if(ev.target && ev.target.id === 'traceClose'){ closeTraceDrawer(); }
});

async function loadTrace(traceId){
  if(!traceId) return;
  const url = API + '/admin/trace/' + encodeURIComponent(traceId) + '/spans';
  const r = await fetch(url, {headers: {'X-API-Key': localStorage.API_KEY || ''}});
  if(!r.ok){ console.error(await r.text()); return; }
  const j = await r.json();
  const spans = j.spans || [];
  const stats = document.getElementById('traceStats');
  if(!spans.length){ stats.textContent = 'No spans for this trace.'; renderTraceBars([]); document.getElementById('traceFlame').innerHTML=''; return; }
  const total = Math.max(...spans.map(s => s.offset + s.duration));
  stats.textContent = `Spans: ${spans.length}   Total: ${total.toFixed(3)}s`;
  // Flame-like bars
  const container = document.getElementById('traceFlame');
  container.innerHTML = '';
  spans.forEach(s => {
    const row = document.createElement('div');
    row.className = 'flex items-center gap-2 mb-1';
    const label = document.createElement('div');
    label.className = 'w-40 text-xs truncate';
    label.textContent = s.name;
    const barWrap = document.createElement('div');
    barWrap.className = 'flex-1 relative h-3 bg-slate-800 rounded';
    const startPct = (s.offset / total) * 100;
    const widthPct = (s.duration / total) * 100;
    const bar = document.createElement('div');
    bar.className = 'absolute top-0 h-3 rounded bg-indigo-500/70';
    bar.style.left = `${startPct}%`; bar.style.width = `${widthPct}%`;
    barWrap.appendChild(bar);
    const dur = document.createElement('div');
    dur.className = 'w-16 text-right text-xs opacity-70';
    dur.textContent = s.duration.toFixed(3)+'s';
    row.appendChild(label); row.appendChild(barWrap); row.appendChild(dur);
    container.appendChild(row);
  });
  renderTraceBars(spans);
  const csv = API + '/admin/export/trace_spans.csv?trace_id=' + encodeURIComponent(traceId);
  document.getElementById('traceCsv').href = csv;
}

function renderTraceBars(spans){
  const {ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid} = Recharts;
  const data = spans.map(s => ({name: s.name, duration: s.duration}));
  const mount = document.getElementById('traceBars');
  ReactDOM.render(
    React.createElement(ResponsiveContainer, {width:"100%", height:160},
      React.createElement(BarChart, {data},
        React.createElement(CartesianGrid, {strokeDasharray:"3 3"}),
        React.createElement(XAxis, {dataKey:"name", hide:true}),
        React.createElement(YAxis, {}),
        React.createElement(Tooltip, {}),
        React.createElement(Bar, {dataKey:"duration"})
      )
    ), mount
  );
}

document.addEventListener('click', (ev)=>{
  if(ev.target && ev.target.matches('[data-open-trace]')){
    openTraceDrawer();
    const v = ev.target.getAttribute('data-trace-id') || '';
    document.getElementById('traceInput').value = v;
    if(v) loadTrace(v);
  }
});
document.getElementById('traceLoad')?.addEventListener('click', ()=>{
  const v = document.getElementById('traceInput').value.trim();
  loadTrace(v);
});
// Optionally expose a global opener
window.openTrace = (traceId)=>{ openTraceDrawer(); document.getElementById('traceInput').value = traceId||''; if(traceId) loadTrace(traceId); };


// ---- Trace: tree + critical path + filters ----
let TRACE_FILTER = {persona:null, tool:null};
let TRACE_LAST_ID = null;
let TRACE_LAST_SPANS = [];

function buildSpanTree(spans){
  // containment-based tree (nested intervals)
  const sorted = spans.slice().sort((a,b)=> a.start===b.start ? (b.end-a.end) : (a.start-b.start));
  const root = {children:[], depth:0, name:'root'};
  const stack = [root];
  for(const s of sorted){
    while(stack.length>1 && s.start >= stack[stack.length-1].end){
      stack.pop();
    }
    while(stack.length>1 && !(s.start >= stack[stack.length-1].start && s.end <= stack[stack.length-1].end)){
      stack.pop();
    }
    const node = {...s, children:[], depth: stack.length-1};
    stack[stack.length-1].children.push(node);
    stack.push(node);
  }
  return root;
}
function renderTree(node, mount){
  mount.innerHTML = '';
  function row(n){
    if(!n || !n.children) return;
    for(const c of n.children){
      const div = document.createElement('div');
      div.className = 'mb-1';
      const pad = document.createElement('span');
      pad.innerHTML = '&nbsp;'.repeat(c.depth*2);
      const label = document.createElement('span');
      label.textContent = `${c.name} (${(c.duration||0).toFixed(3)}s)`;
      if(TRACE_CRIT_IDS && TRACE_CRIT_IDS.has(c.span_id)) label.className='text-indigo-300';
      div.appendChild(pad); div.appendChild(label);
      mount.appendChild(div);
      row(c, mount);
    }
  }
  row(node, mount);
}

let TRACE_CRIT_IDS = null;

async function loadCritical(traceId){
  const r = await fetch(API + '/admin/trace/' + encodeURIComponent(traceId) + '/critical_path', {headers: {'X-API-Key': localStorage.API_KEY || ''}});
  if(!r.ok) return {spans:[], total_duration:0};
  const j = await r.json();
  const ids = new Set(j.spans.map(s=>s.span_id));
  TRACE_CRIT_IDS = ids;
  const el = document.getElementById('critSummary');
  el.textContent = `critical: ${j.spans.length} spans, total ${j.total_duration.toFixed(3)}s`;
  document.getElementById('critCsv').onclick = ()=>{
    const url = API + '/admin/export/critical_path.csv?trace_id=' + encodeURIComponent(traceId);
    const a = document.createElement('a'); a.href = url; a.target='_blank'; a.click();
  };
  return j;
}

function applyTraceFilter(spans){
  return spans.filter(s => (!TRACE_FILTER.persona || s.persona===TRACE_FILTER.persona) &&
                           (!TRACE_FILTER.tool || s.tool===TRACE_FILTER.tool));
}

async function loadTrace(traceId){
  TRACE_LAST_ID = traceId;
  const url = API + '/admin/trace/' + encodeURIComponent(traceId) + '/spans';
  const r = await fetch(url, {headers: {'X-API-Key': localStorage.API_KEY || ''}});
  if(!r.ok){ console.error(await r.text()); return; }
  const j = await r.json();
  TRACE_LAST_SPANS = j.spans || [];
  await loadCritical(traceId);
  renderTraceWithState();
}

function renderTraceWithState(){
  const spansAll = TRACE_LAST_SPANS;
  const spans = document.getElementById('onlyCritical')?.checked && TRACE_CRIT_IDS
      ? spansAll.filter(s=>TRACE_CRIT_IDS.has(s.span_id))
      : applyTraceFilter(spansAll);

  // Flame bars
  const stats = document.getElementById('traceStats');
  if(!spans.length){ stats.textContent='No spans for view.'; document.getElementById('traceFlame').innerHTML=''; renderTraceBars([]); document.getElementById('traceTree').innerHTML=''; return; }
  const total = Math.max(...spans.map(s => (s.offset||0) + (s.duration||0)));
  stats.textContent = `Spans: ${spans.length}   Total: ${total.toFixed(3)}s`;
  const container = document.getElementById('traceFlame');
  container.innerHTML='';
  spans.forEach(s=>{
    const row = document.createElement('div');
    row.className = 'flex items-center gap-2 mb-1';
    const label = document.createElement('div');
    label.className = 'w-40 text-xs truncate';
    label.textContent = s.name;
    const barWrap = document.createElement('div'); barWrap.className='flex-1 relative h-3 bg-slate-800 rounded';
    const startPct = (s.offset/total)*100; const widthPct = (s.duration/total)*100;
    const bar = document.createElement('div'); bar.className='absolute top-0 h-3 rounded ' + (TRACE_CRIT_IDS && TRACE_CRIT_IDS.has(s.span_id) ? 'bg-amber-500/80' : 'bg-indigo-500/70');
    bar.style.left = `${startPct}%`; bar.style.width = `${widthPct}%`;
    barWrap.appendChild(bar);
    const dur = document.createElement('div'); dur.className='w-16 text-right text-xs opacity-70'; dur.textContent=(s.duration||0).toFixed(3)+'s';
    row.appendChild(label); row.appendChild(barWrap); row.appendChild(dur);
    container.appendChild(row);
  });
  renderTraceBars(spans);
  // Tree
  renderTree(buildSpanTree(spans), document.getElementById('traceTree'));
}

// filter controls
document.getElementById('onlyCritical')?.addEventListener('change', renderTraceWithState);
document.addEventListener('click', (ev)=>{
  if(ev.target && ev.target.matches('[data-filter-persona]')){
    TRACE_FILTER.persona = ev.target.getAttribute('data-filter-persona') || null;
    renderTraceWithState();
  }
  if(ev.target && ev.target.matches('[data-filter-tool]')){
    TRACE_FILTER.tool = ev.target.getAttribute('data-filter-tool') || null;
    renderTraceWithState();
  }
});


// Routing
const pageSemantic = document.getElementById('pageSemanticSearch');
const pageRefactor = document.getElementById('pageRefactor');
const navSemantic = document.getElementById('navSemanticSearch');
const navRefactor = document.getElementById('navRefactor');
function showPage(el){
  document.querySelectorAll('main section').forEach(s=> s.classList.add('hidden'));
  el.classList.remove('hidden');
}
navSemantic?.addEventListener('click', ()=> showPage(pageSemantic));
navRefactor?.addEventListener('click', ()=> showPage(pageRefactor));

// Semantic search
async function runSemanticSearch(){
  const q = document.getElementById('scQuery').value.trim();
  const mode = document.getElementById('scMode').value;
  if(!q) return;
  const r = await fetch(API.replace(/\/$/,'') + '/search/code?q=' + encodeURIComponent(q) + '&mode=' + encodeURIComponent(mode), {
    headers: {'X-API-Key': localStorage.API_KEY || ''}
  });
  const out = document.getElementById('scResults');
  const stats = document.getElementById('scStats');
  out.innerHTML='';
  if(!r.ok){ out.textContent = await r.text(); return; }
  const j = await r.json();
  stats.textContent = `Top ${j.top_k} • mode=${j.mode}`;
  (j.results || []).forEach(rec => {
    const card = document.createElement('div');
    card.className = 'border border-slate-800 rounded p-2';
    const h = document.createElement('div');
    h.className = 'text-xs opacity-80 mb-1';
    h.textContent = `${rec.path} • score=${Number(rec.score).toFixed(4)}`;
    const pre = document.createElement('pre');
    pre.className = 'bg-slate-950 border border-slate-900 rounded p-2 overflow-auto text-xs';
    pre.textContent = rec.snippet || '';
    card.appendChild(h); card.appendChild(pre);
    out.appendChild(card);
  });
}
document.getElementById('scGo')?.addEventListener('click', runSemanticSearch);

// Refactor
async function rfPreview(){
  const path = document.getElementById('rfPath').value.trim();
  const instr = document.getElementById('rfInstr').value.trim();
  const msg = document.getElementById('rfMsg');
  const pre = document.getElementById('rfPatch');
  pre.textContent=''; msg.textContent='';
  const r = await fetch(API.replace(/\/$/,'') + '/refactor/preview?file_path=' + encodeURIComponent(path) + '&instruction=' + encodeURIComponent(instr), {
    method:'POST',
    headers: {'X-API-Key': localStorage.API_KEY || ''}
  });
  if(!r.ok){ pre.textContent = await r.text(); return; }
  const j = await r.json();
  pre.textContent = JSON.stringify(j, null, 2);
  msg.textContent = 'Validated patch ready to apply.';
  window._RF_LAST = j;
}
async function rfApply(){
  if(!window._RF_LAST){ document.getElementById('rfMsg').textContent='No preview yet.'; return; }
  const r = await fetch(API.replace(/\/$/,'') + '/refactor/apply', {
    method:'POST',
    headers: {'Content-Type':'application/json','X-API-Key': localStorage.API_KEY || ''},
    body: JSON.stringify(window._RF_LAST)
  });
  const msg = document.getElementById('rfMsg');
  if(!r.ok){ msg.textContent = await r.text(); return; }
  const j = await r.json();
  msg.textContent = 'Applied: ' + (j.applied || []).join(', ');
}
document.getElementById('rfPreview')?.addEventListener('click', rfPreview);
document.getElementById('rfApply')?.addEventListener('click', rfApply);


async function showToast(msg){
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.style.display = 'block';
  setTimeout(()=>{ t.style.display='none'; }, 2500);
}

async function runPipeline(){
  const btn = document.getElementById('runBtn');
  const out = document.getElementById('out');
  btn.disabled = true; btn.textContent = 'Running...';
  try {
    const res = await fetch('http://localhost:8002/orchestrate/run', { method:'POST' });
    if(!res.ok){
      const txt = await res.text();
      throw new Error('Run failed: ' + res.status + ' ' + txt);
    }
    const data = await res.json();
    out.textContent = JSON.stringify(data, null, 2);
    showToast('Run complete ✔');
  } catch(e){
    showToast('Error: ' + e.message);
  } finally {
    btn.disabled = false; btn.textContent = 'Run ⏵';
  }
}
document.getElementById('runBtn').addEventListener('click', runPipeline);

import Link from 'next/link'
export default async function Page() {
  // Use server-side fetch to get stats via Next API proxy
  let stats = null;
  try {
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:3000'}/api/ledger/stats`, { cache: 'no-store' });
    if (res.ok) stats = await res.json();
  } catch(e){}
  return (
    <main style={{padding:20, background:'#071025', color:'#e6eef8', minHeight:'100vh'}}>
      <h1>AI Code Agent — App Router Home</h1>
      <div style={{marginTop:10}}>
        <Link href="/dashboard"><a style={{color:'#7dd3fc'}}>Dashboard</a></Link> | <Link href="/editor"><a style={{color:'#7dd3fc'}}>Editor</a></Link> | <Link href="/monaco"><a style={{color:'#7dd3fc'}}>Monaco</a></Link> | <Link href="/artifacts"><a style={{color:'#7dd3fc'}}>Artifacts</a></Link> | <Link href="/rag"><a style={{color:'#7dd3fc'}}>RAG Demo</a></Link> | <Link href="/login"><a style={{color:'#7dd3fc'}}>Login</a></Link>
      </div>
      <pre style={{marginTop:20}}>{JSON.stringify(stats, null, 2)}</pre>
    </main>
  )
}


function _showToast(msg){
  const el = document.getElementById('toast');
  if(!el){ console.log('TOAST:', msg); return; }
  el.textContent = msg; el.style.display = 'block';
  setTimeout(()=>{ el.style.display='none'; }, 3500);
}

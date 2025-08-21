'use client'

import { useState, useEffect, useRef, useMemo } from 'react'

// Recharts will be dynamically imported to avoid SSR issues if not installed.
const Recharts = {
  BarChart: () => null, Bar: () => null, XAxis: () => null, YAxis: () => null,
  Tooltip: () => null, ResponsiveContainer: () => null, PieChart: () => null,
  Pie: () => null, Cell: () => null, Legend: () => null,
}

let rechartsImported = false

async function loadRecharts() {
  if (rechartsImported) return true
  try {
    const R = await import('recharts')
    Recharts.BarChart = R.BarChart
    Recharts.Bar = R.Bar
    Recharts.XAxis = R.XAxis
    Recharts.YAxis = R.YAxis
    Recharts.Tooltip = R.Tooltip
    Recharts.ResponsiveContainer = R.ResponsiveContainer
    Recharts.PieChart = R.PieChart
    Recharts.Pie = R.Pie
    Recharts.Cell = R.Cell
    Recharts.Legend = R.Legend
    rechartsImported = true
    return true
  } catch (e) {
    console.warn('Recharts not installed. Install with `npm install recharts` to enable charts.', e)
    return false
  }
}

const defaultPlan = {
  plan_id: 'demo',
  steps: [{
    step_id: 's1', description: 'summarize', persona: 'summarizer', tool: 'summarize_tokens', payload: { context_blocks: ['example'] },
  }, {
    step_id: 's2', description: 'generate code', persona: 'coder', tool: 'generate_code', payload: { step_id: 's2', files_requested: [] },
  }]
}

export default function OrchestratorPage() {
  const [planText, setPlanText] = useState(JSON.stringify(defaultPlan, null, 2))
  const [runId, setRunId] = useState(null)
  const [runData, setRunData] = useState(null)
  const [chartsOk, setChartsOk] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const evtRef = useRef(null)

  useEffect(() => {
    loadRecharts().then(setChartsOk)
  }, [])

  const clearRun = () => {
    if (evtRef.current) {
      evtRef.current.close()
      evtRef.current = null
    }
    setRunId(null)
    setRunData(null)
    setError(null)
  }

  async function startRun() {
    clearRun()
    setLoading(true)
    try {
      const plan = JSON.parse(planText)
      const res = await fetch('/api/orchestrator/orchestrate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plan })
      })
      if (!res.ok) {
        const errData = await res.json().catch(() => ({ detail: `HTTP Error: ${res.status}`}))
        throw new Error(errData.detail)
      }
      const j = await res.json()
      setRunId(j.run_id)
      listenRun(j.run_id)
    } catch (e) {
      setError(`Failed to start run: ${e.message}`)
    } finally {
      setLoading(false)
    }
  }

  function listenRun(id) {
    const url = `/api/orchestrator/runs/stream/${id}`
    const es = new EventSource(url)
    evtRef.current = es
    es.onmessage = (e) => {
      try {
        const d = JSON.parse(e.data)
        setRunData(d)
      } catch (err) {
        console.error("Failed to parse SSE data:", err)
        setError("Failed to parse live update from server.")
      }
    }
    es.onerror = () => {
      setError("Connection to live updates failed.")
      es.close()
    }
  }

  const { stepTimingData, personaCostData } = useMemo(() => {
    if (!runData?.trace?.steps) return { stepTimingData: [], personaCostData: [] }

    const steps = runData.trace.steps
    const stepTiming = steps.map((s, idx) => {
      const dur = s.result?.duration ?? (s.ended_at && s.started_at ? s.ended_at - s.started_at : 0)
      return { name: s.description || s.step_id || `step${idx}`, duration: Math.round(dur * 1000) }
    })

    const costMap = {}
    steps.forEach(s => {
      const persona = s.persona ?? s.result?.response?.persona ?? 'unknown'
      const cost = s.result?.response?.cost ?? s.result?.response?.cost_est ?? (s.result?.response?.token_est ? Number(s.result.response.token_est) * 0.000002 : 0)
      costMap[persona] = (costMap[persona] || 0) + Number(cost || 0)
    })
    const personaCost = Object.entries(costMap).map(([name, value]) => ({ name, value: Number(value.toFixed(8)) }))

    return { stepTimingData: stepTiming, personaCostData: personaCost }
  }, [runData])

  return (
    <div style={{ padding: 20, background: '#071025', color: '#e6eef8', minHeight: '100vh' }}>
      <h1>Orchestrator Playground — Visuals</h1>
      <div style={{ display: 'flex', gap: 12 }}>
        <textarea
          value={planText}
          onChange={e => setPlanText(e.target.value)}
          style={{ width: 520, height: 320, background: '#1e293b', color: 'white', border: '1px solid #374151', fontFamily: 'monospace' }}
          disabled={loading}
        />
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={startRun} style={{ padding: 8, background: '#10b981', cursor: 'pointer', opacity: loading ? 0.5 : 1 }} disabled={loading}>
              {loading ? 'Running...' : 'Run Plan'}
            </button>
            <button onClick={clearRun}>Clear</button>
          </div>
          {error && <div style={{ color: '#f87171', marginTop: 12 }}>{error}</div>}
          <div style={{ marginTop: 12 }}><strong>Run ID:</strong> {runId}</div>
          <div style={{ marginTop: 12 }}><strong>State:</strong> {runData ? runData.state : 'n/a'}</div>
        </div>
      </div>

      <div style={{ marginTop: 20, display: 'grid', gridTemplateColumns: '1fr 400px', gap: 20 }}>
        <div style={{ background: '#041226', padding: 12, borderRadius: 8 }}>
          <h3>Per-step timing (ms)</h3>
          {chartsOk ? (
            <Recharts.ResponsiveContainer width='100%' height={240}>
              <Recharts.BarChart data={stepTimingData}>
                <Recharts.XAxis dataKey='name' stroke='#9ca3af' />
                <Recharts.YAxis stroke='#9ca3af' />
                <Recharts.Tooltip />
                <Recharts.Bar dataKey='duration' fill='#06b6d4' />
              </Recharts.BarChart>
            </Recharts.ResponsiveContainer>
          ) : (
            <div style={{ padding: 12, color: '#9ca3af' }}>Install recharts to see charts</div>
          )}
        </div>

        <div style={{ background: '#041226', padding: 12, borderRadius: 8 }}>
          <h3>Per-persona cost breakdown</h3>
          {chartsOk ? (
            <Recharts.ResponsiveContainer width='100%' height={240}>
              <Recharts.PieChart>
                <Recharts.Pie data={personaCostData} dataKey='value' nameKey='name' cx='50%' cy='50%' outerRadius={80} label>
                  {personaCostData.map((entry, index) => (
                    <Recharts.Cell key={`cell-${index}`} fill={['#06b6d4', '#10b981', '#f59e0b', '#ef4444'][index % 4]} />
                  ))}
                </Recharts.Pie>
                <Recharts.Tooltip />
                <Recharts.Legend />
              </Recharts.PieChart>
            </Recharts.ResponsiveContainer>
          ) : (
            <div style={{ padding: 12, color: '#9ca3af' }}>Install recharts to see charts</div>
          )}
        </div>
      </div>

      <div style={{ marginTop: 20, background: '#031021', padding: 12, borderRadius: 8 }}>
        <h3>Run Trace</h3>
        <pre style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify(runData, null, 2)}</pre>
      </div>
    </div>
  )
}

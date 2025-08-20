
import { test, expect } from '@playwright/test';

test('happy path RAG -> Orchestrator -> Ledger', async ({ request }) => {
  const base = process.env.BASE_URL ? process.env.BASE_URL.replace(/\/$/, '') : 'http://localhost:8000';
  const retrieval_base = process.env.RETRIEVAL_URL ? process.env.RETRIEVAL_URL.replace(/\/$/, '') : 'http://localhost:8002';
  const ledger_base = process.env.LEDGER_URL ? process.env.LEDGER_URL.replace(/\/$/, '') : 'http://localhost:8003';

  // 1) RAG search (should return 200 with retrieved)
  const ragRes = await request.post(retrieval_base + '/search', { data: { query: 'test vector', top_k: 3 } });
  expect(ragRes.status()).toBeLessThan(400);
  const rag = await ragRes.json();
  expect(rag.retrieved || rag.results).toBeTruthy();

  // 2) Orchestrator run (smoke): POST /run or /apply_patches depending on API
  let runRes = await request.post(base + '/run', { data: { goal: 'noop' } });
  if (runRes.status() >= 400) {
    // try apply_patches as fallback
    runRes = await request.post(base + '/apply_patches', { data: { plan_id: 'p1', step_id: 's1', patches: [] } });
  }
  expect(runRes.status()).toBeLessThan(500);

  // 3) Ledger stats
  const stats = await request.get(ledger_base + '/stats');
  expect(stats.status()).toBeLessThan(400);
  const st = await stats.json();
  expect(st.totals).toBeTruthy();
});

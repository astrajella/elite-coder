import { test, expect } from '@playwright/test';

test('happy path: RAG search + ledger stats + orchestrator run', async ({ request }) => {
  const q = 'vector store adapter';
  const rag = await request.get('process.env.BASE_URL ? process.env.BASE_URL.replace(/\/$/, '') : 'http://localhost:8002'/search/code', { params: { q, top_k: 3, mode: 'hybrid' } });
  expect(rag.status()).toBeLessThan(400);
  const data = await rag.json();
  expect(data.results || data.retrieved).toBeTruthy();

  const stats = await request.get('process.env.BASE_URL ? process.env.BASE_URL.replace(/\/$/, '') : 'http://localhost:8003'/ledger/stats');
  expect(stats.status()).toBeLessThan(400);
  const st = await stats.json();
  expect(st.totals || st.total).toBeTruthy();

  const run = await request.post('process.env.BASE_URL ? process.env.BASE_URL.replace(/\/$/, '') : 'http://localhost:8000'/run', { data: { goal: 'noop' } });
  expect(run.status()).toBeLessThan(500);
});

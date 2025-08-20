import { test, expect } from '@playwright/test';

test('/api/file blocks directory traversal', async ({ request }) => {
  const bad = await request.get('process.env.BASE_URL ? process.env.BASE_URL.replace(/\/$/, '') : 'http://localhost:8000'/api/file?path=../../etc/passwd');
  expect(bad.status()).toBe(403);
});

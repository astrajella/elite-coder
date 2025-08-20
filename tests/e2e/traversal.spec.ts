
// @ts-check
import { test, expect } from '@playwright/test';

const BASE = process.env.BASE_URL || 'http://localhost:8000';

test('api/file traversal is rejected', async ({ request }) => {
  const res = await request.get(`${BASE}/api/file?path=../../etc/passwd`);
  expect(res.status()).toBeGreaterThanOrEqual(400);
});

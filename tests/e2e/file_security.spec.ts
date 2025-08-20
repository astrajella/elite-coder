
import { test, expect } from '@playwright/test';

test('api/file blocks traversal', async ({ request }) => {
  const url = 'http://localhost:8003/api/file?path=../../etc/passwd';
  const res = await request.get(url);
  expect(res.status()).toBe(403);
});

const { test, expect } = require('@playwright/test');

test('commit and download artifact', async ({ page, request }) => {
  // login via API
  const login = await request.post('http://127.0.0.1:8001/auth/login', { form: { username: 'dev', password: 'pass' } });
  expect(login.status()).toBe(200);
  const body = await login.json();
  const token = body.access_token;
  // set token in localStorage by visiting login page and injecting
  await page.goto('http://localhost:3000/login');
  await page.evaluate((t) => localStorage.setItem('ai_token', t), token);
  // go to monaco and commit patches
  await page.goto('http://localhost:3000/monaco');
  await page.click('text=Commit Patches');
  // wait for commit result to appear
  await page.waitForSelector('text/ok', { timeout: 5000 });
  // go to artifacts page and click first artifact link
  await page.goto('http://localhost:3000/artifacts');
  const href = await page.getAttribute('a', 'href');
  expect(href).toContain('/api/agent/artifacts/download');
});

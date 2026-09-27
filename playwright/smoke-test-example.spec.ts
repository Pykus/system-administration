import { test, expect } from '@playwright/test';

test('local application exposes a usable landing page', async ({ page }) => {
  const baseURL = process.env.APP_URL ?? 'http://127.0.0.1:8000';
  const response = await page.goto(baseURL);
  expect(response, 'navigation should return an HTTP response').not.toBeNull();
  expect(response!.ok(), 'landing page should return 2xx').toBeTruthy();
  await expect(page.locator('body')).not.toBeEmpty();
});

test('missing route fails explicitly instead of looking healthy', async ({ request }) => {
  const baseURL = process.env.APP_URL ?? 'http://127.0.0.1:8000';
  const response = await request.get(baseURL + '/__smoke_missing__');
  expect(response.status()).toBeGreaterThanOrEqual(400);
});

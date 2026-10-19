import { test, expect } from '@playwright/test';
import { build } from 'esbuild';
import path from 'node:path';

let script;
test.beforeAll(async () => {
    const result = await build({
        entryPoints: ['tests/ui/reader-fixture.jsx'],
        bundle: true, write: false, format: 'iife',
        tsconfigRaw: { compilerOptions: { jsx: 'react-jsx' } },
        alias: {
            '@decky/api': path.resolve('tests/ui/decky-mock.js'),
            '@decky/ui': path.resolve('tests/ui/decky-mock.js'),
        },
        define: { 'process.env.NODE_ENV': '"test"' },
    });
    script = result.outputFiles[0].text;
});

test.beforeEach(async ({ page }) => {
    // All runtime assets and dictionary responses come from the bundle/mocks.
    await page.route('**/*', route => route.abort());
    await page.setContent('<html><body style="margin:0"><div id="root"></div></body></html>');
    await page.addScriptTag({ content: script });
});

test('positions hit targets using screenshot scale and keeps coarse words selectable', async ({ page }) => {
    const cat = page.locator('button[aria-label="猫 ねこ"]');
    await expect(cat).toBeVisible();
    const box = await cat.boundingBox();
    expect(box.x).toBe(50);
    expect(box.y).toBe(50);
    expect(box.width).toBe(20);
    await expect(page.getByRole('button', { name: /犬.*いぬ/ })).toBeVisible();
    await cat.click();
    await expect(page.getByRole('status')).toContainText('cat');
});

test('ignores stale lookups and reuses cached definitions', async ({ page }) => {
    await page.locator('button[aria-label="猫 ねこ"]').click();
    await expect.poll(() => page.evaluate(() => window.readerCalls.length)).toBe(1);
    await page.getByRole('button', { name: /犬.*いぬ/ }).click();
    await expect(page.getByRole('status')).toContainText('dog');
    await page.waitForTimeout(200);
    await expect(page.getByRole('status')).not.toContainText('cat');
    await page.locator('button[aria-label="猫 ねこ"]').click();
    await expect(page.getByRole('status')).toContainText('cat');
    expect(await page.evaluate(() => window.readerCalls.length)).toBe(2);
});

test('navigation selects words, closes definitions, and exits', async ({ page }) => {
    await page.getByRole('button', { name: 'Previous', exact: true }).click();
    await expect(page.getByRole('status')).toContainText('dog');
    await page.getByRole('button', { name: 'Next', exact: true }).click();
    await expect(page.getByRole('status')).toContainText('cat');
    await page.getByRole('button', { name: 'Close meaning', exact: true }).click();
    await expect(page.getByRole('status')).toHaveCount(0);
    await page.getByRole('button', { name: 'Exit', exact: true }).click();
    expect(await page.evaluate(() => window.readerDismissed)).toBe(true);
});

test('shows dictionary errors without closing the reading overlay', async ({ page }) => {
    await page.evaluate(() => { window.readerFailure = true; });
    await page.locator('button[aria-label="猫 ねこ"]').click();
    await expect(page.getByRole('status')).toContainText('Dictionary unavailable');
    await expect(page.getByRole('button', { name: 'Next', exact: true })).toBeVisible();
    expect(await page.evaluate(() => window.readerDismissed)).toBe(false);
});


test('grouped hit targets and grammar-only words support selection and navigation', async ({ page }) => {
    await page.evaluate(() => window.readerShowGroups());
    await page.locator('button[aria-label="思っていた おもっていた"]').click();
    await expect(page.getByRole('status')).toContainText('Inflected vocabulary');
    await expect(page.getByRole('status')).toContainText('to think');
    await expect(page.getByRole('status')).toContainText('〜ていた');
    expect(await page.evaluate(() => window.readerCalls[0].lemma)).toBe('思う');
    await page.getByRole('button', { name: 'Next', exact: true }).click();
    await expect(page.getByRole('status')).toContainText('Grammar expression');
    await expect(page.getByRole('status')).toContainText('agreement or realization');
    await expect(page.getByRole('status')).not.toContainText('No English dictionary entry');
    expect(await page.evaluate(() => window.readerCalls.length)).toBe(1);
    await expect(page.getByRole('button', { name: /じゃないか.*じゃないか/ })).toBeVisible();
    await page.getByRole('button', { name: 'Previous', exact: true }).click();
    await expect(page.getByRole('status')).toContainText('to think');
    expect(await page.evaluate(() => window.readerCalls.length)).toBe(1);
});

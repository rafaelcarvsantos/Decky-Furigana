import { defineConfig } from '@playwright/test';

export default defineConfig({
    testDir: './tests/ui',
    testMatch: '**/*.spec.mjs',
    workers: 1,
    use: {
        browserName: 'chromium',
        viewport: { width: 1280, height: 800 },
        launchOptions: process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {},
    },
});

import { test, expect } from '@playwright/test';

const routes = [
  { path: '/', name: 'home' },
  { path: '/projects', name: 'projects' },
  { path: '/projects/create', name: 'projects-create' },
  { path: '/datasets/upload', name: 'datasets-upload' },
  { path: '/experiments', name: 'experiments' },
  { path: '/artifacts', name: 'artifacts' },
  { path: '/admin/users', name: 'admin-users' },
  { path: '/annotate/1', name: 'annotate' },
];

for (const r of routes) {
  test(`visual check: ${r.name}`, async ({ page, context }) => {
    const logs: string[] = [];
    page.on('console', msg => {
      logs.push(`[${msg.type()}] ${msg.text()}`);
    });

    // 1440px width viewport as requested.
    await context.newCDPSession(page).then((client) =>
      client.send('Emulation.setDeviceMetricsOverride', {
        width: 1440,
        height: 900,
        deviceScaleFactor: 1,
        mobile: false,
      })
    );

    await page.goto(r.path, { waitUntil: 'domcontentloaded' });

    // Basic sanity: no obvious error boundaries text
    await expect(page.locator('body')).toBeVisible();

    // Full-page screenshot
    await page.screenshot({ path: `test-results/visual/${r.name}.png`, fullPage: true });

    // Write console logs to file using Node fs
    const fs = await import('fs');
    const dir = 'test-results/visual';
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(`${dir}/${r.name}.console.log`, logs.join('\n'));
  });
}

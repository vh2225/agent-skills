// Opens headed Chrome with a persistent ./profile so YOU can sign in by hand.
// The script never types credentials; it only waits until a signed-in signal appears.
// Usage: node login.mjs <app-url> [css-selector-that-only-exists-when-signed-in]
// Example: node login.mjs https://app.example.com/ "text=Dashboard"
import { chromium } from "playwright";

const url = process.argv[2];
const signal = process.argv[3]; // optional
if (!url) { console.error("usage: node login.mjs <app-url> [signed-in selector]"); process.exit(1); }

const ctx = await chromium.launchPersistentContext("./profile", {
  channel: "chrome", headless: false, viewport: { width: 1440, height: 900 },
});
const page = ctx.pages()[0] ?? await ctx.newPage();
await page.goto(url);
console.log("Sign in in the Chrome window (waiting up to 10 min)...");

const deadline = Date.now() + 10 * 60_000;
let ok = false;
while (Date.now() < deadline) {
  ok = signal
    ? await page.locator(signal).first().isVisible().catch(() => false)
    : !/login|sign-?in|auth/i.test(page.url()); // fallback: left the sign-in pages
  if (ok) break;
  await page.waitForTimeout(3000);
}
const where = new URL(page.url()); // print origin + path only: query strings can carry auth codes
await ctx.close();
if (!ok) { console.error("Timed out waiting for sign-in at", where.origin + where.pathname); process.exit(1); }
console.log("Signed in. Session saved in ./profile (keep it private). Page:", where.origin + where.pathname);

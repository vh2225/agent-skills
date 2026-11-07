// Recording kit: real browser, visible cursor + click ripple, beats timed to narration.
import { chromium } from "playwright";
import { readFileSync, writeFileSync, mkdirSync, renameSync } from "node:fs";

const CURSOR_JS = `
(() => {
  if (window.__demoCursor) return; window.__demoCursor = true;
  const add = () => {
    const c = document.createElement('div'); c.id='__dc';
    c.style.cssText='position:fixed;left:0;top:0;width:22px;height:22px;margin:-11px 0 0 -11px;border-radius:50%;background:rgba(20,20,20,.28);border:2px solid #fff;box-shadow:0 1px 6px rgba(0,0,0,.35);z-index:2147483647;pointer-events:none;transition:transform .12s';
    document.documentElement.appendChild(c);
    addEventListener('mousemove', e => { c.style.left=e.clientX+'px'; c.style.top=e.clientY+'px'; }, true);
    addEventListener('mousedown', e => { c.style.transform='scale(.75)';
      const r=document.createElement('div'); r.style.cssText='position:fixed;left:'+e.clientX+'px;top:'+e.clientY+'px;width:10px;height:10px;margin:-5px 0 0 -5px;border-radius:50%;border:3px solid rgba(37,99,235,.85);z-index:2147483646;pointer-events:none;transition:all .5s ease-out';
      document.documentElement.appendChild(r); requestAnimationFrame(()=>{r.style.width=r.style.height='56px';r.style.margin='-28px 0 0 -28px';r.style.opacity='0';}); setTimeout(()=>r.remove(),600); }, true);
    addEventListener('mouseup', () => { c.style.transform=''; }, true);
    // Native title tooltips don't appear in screen captures; mirror them in a visible bubble.
    const tip = document.createElement('div'); tip.style.cssText='position:fixed;max-width:340px;padding:8px 11px;border-radius:8px;background:#1d2733;color:#fff;font:13px/1.4 -apple-system,Helvetica,sans-serif;z-index:2147483645;pointer-events:none;opacity:0;transition:opacity .2s;box-shadow:0 4px 14px rgba(0,0,0,.25)';
    document.documentElement.appendChild(tip); let tipT;
    addEventListener('mouseover', e => { const el = e.target.closest && e.target.closest('[title]'); clearTimeout(tipT); tip.style.opacity='0';
      if (!el || !el.getAttribute('title')) return; tipT = setTimeout(() => { tip.textContent = el.getAttribute('title');
        tip.style.left = Math.min(e.clientX + 14, innerWidth - 360) + 'px'; tip.style.top = (e.clientY + 22) + 'px'; tip.style.opacity='1'; }, 450); }, true);
  };
  if (document.documentElement) add(); else addEventListener('DOMContentLoaded', add);
})();`;

const BLUR_EMAILS_JS = `
(() => {
  const re = /[\\w.+-]+@[\\w-]+\\.[\\w.]+/;
  // Best effort only: covers text nodes and form field values, not images, canvas or video.
  // Record with sample data; never rely on blurring to hide real personal data.
  const blur = (el) => { if (el && !el.dataset.blurred) { el.dataset.blurred = '1'; el.style.filter = 'blur(6px)'; } };
  const scan = () => { const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    for (let n; (n = w.nextNode());) if (re.test(n.nodeValue)) blur(n.parentElement);
    for (const el of document.querySelectorAll('input, textarea')) if (re.test(el.value || '')) blur(el); };
  addEventListener('DOMContentLoaded', () => { scan(); new MutationObserver(scan).observe(document.body, { subtree: true, childList: true, characterData: true }); });
  addEventListener('input', scan, true);
})();`;

export async function startRecording({ name, viewport, scale = 2, css = "", profile = "./profile" }) {
  mkdirSync(`out/${name}`, { recursive: true });
  const durs = JSON.parse(readFileSync(`out/${name}/audio/durations.json`, "utf8"));
  const ctx = await chromium.launchPersistentContext(profile, {
    // Headed by default: headless screencast is 1x only. HEADLESS=1 to override.
    channel: "chrome", headless: Boolean(process.env.HEADLESS), viewport, deviceScaleFactor: scale,
  });
  await ctx.addInitScript(CURSOR_JS);
  await ctx.addInitScript(BLUR_EMAILS_JS);
  if (css) await ctx.addInitScript(`addEventListener('DOMContentLoaded',()=>{const s=document.createElement('style');s.textContent=${JSON.stringify(css)};document.head.appendChild(s);});`);
  const page = ctx.pages()[0] ?? await ctx.newPage();
  // Crisp capture: Chrome's screencast at device pixels; frames carry wall-clock timestamps.
  const framesDir = `out/${name}/frames-raw`; mkdirSync(framesDir, { recursive: true });
  const cdp = await ctx.newCDPSession(page);
  const frames = [];
  cdp.on("Page.screencastFrame", async ({ data, sessionId, metadata }) => {
    const f = `${framesDir}/${String(frames.length).padStart(6, "0")}.jpg`;
    writeFileSync(f, Buffer.from(data, "base64"));
    frames.push({ f, ts: metadata.timestamp });
    await cdp.send("Page.screencastFrameAck", { sessionId }).catch(() => {});
  });
  await cdp.send("Page.startScreencast", { format: "jpeg", quality: 92, maxWidth: viewport.width * scale, maxHeight: viewport.height * scale, everyNthFrame: 1 });
  const t0 = Date.now();
  const beats = [];
  let mouse = { x: viewport.width / 2, y: viewport.height / 2 };
  const now = () => (Date.now() - t0) / 1000;

  const api = {
    page,
    // A narrated beat: run actions, then hold until the narration (plus tail) has finished.
    async beat(id, actions = async () => {}, { tail = 0.6, fast = false } = {}) {
      const start = now();
      await actions();
      const need = (durs[id] ?? 0) + tail;
      const left = need - (now() - start);
      if (left > 0) await page.waitForTimeout(left * 1000);
      beats.push({ id, start, end: now(), fast });
      console.log(`beat ${id} ${start.toFixed(1)}-${now().toFixed(1)}`);
    },
    // Untimed segment (e.g. waiting on the model) that post-production speeds up.
    async fastForward(label, actions) {
      const start = now(); await actions(); beats.push({ id: null, label, start, end: now(), fast: true });
      console.log(`fast ${label} ${start.toFixed(1)}-${now().toFixed(1)}`);
    },
    async moveTo(locator, { steps = 25 } = {}) {
      const el = typeof locator === "string" ? page.locator(locator).first() : locator;
      await el.scrollIntoViewIfNeeded().catch(() => {});
      const b = await el.boundingBox(); if (!b) throw new Error("no box for target");
      const x = b.x + b.width / 2, y = b.y + b.height / 2;
      await page.mouse.move(x, y, { steps }); mouse = { x, y };
      await page.waitForTimeout(250);
      return el;
    },
    async click(locator, opts) { const el = await api.moveTo(locator, opts); await page.mouse.down(); await page.waitForTimeout(90); await page.mouse.up(); await page.waitForTimeout(400); return el; },
    async scrollBy(dy, ms = 1200) { const n = 30; for (let i = 0; i < n; i++) { await page.mouse.wheel(0, dy / n); await page.waitForTimeout(ms / n); } },
    async scrollTo(locator, offset = 90, ms = 900) {
      const el = typeof locator === "string" ? page.locator(locator).first() : locator;
      await el.evaluate((e, off) => scrollTo({ top: e.getBoundingClientRect().top + scrollY - off, behavior: "smooth" }), offset);
      await page.waitForTimeout(ms);
    },
    pause: (s) => page.waitForTimeout(s * 1000),
    async finish() {
      await page.waitForTimeout(300);
      const endTs = Date.now() / 1000;  // a static page sends no frames; hold the last one until here
      await cdp.send("Page.stopScreencast").catch(() => {});
      await ctx.close();
      // ffconcat with per-frame durations; times relative to t0 (seconds).
      const base = t0 / 1000; let txt = "ffconcat version 1.0\n";
      for (let i = 0; i < frames.length; i++) {
        const next = i + 1 < frames.length ? frames[i + 1].ts : Math.max(endTs, frames[i].ts + 0.5);
        txt += `file '${frames[i].f.split("/").pop()}'\nduration ${Math.max(0.001, next - frames[i].ts).toFixed(4)}\n`;
      }
      // ffconcat ignores the last entry's duration unless the file is listed once more.
      txt += `file '${frames[frames.length - 1].f.split("/").pop()}'\n`;
      writeFileSync(`${framesDir}/list.ffconcat`, txt);
      writeFileSync(`out/${name}/capture.json`, JSON.stringify({ firstFrameAt: frames[0].ts - base, count: frames.length }));
      writeFileSync(`out/${name}/beats.json`, JSON.stringify(beats, null, 1));
      console.log("recorded", frames.length, "frames; first at", (frames[0].ts - t0 / 1000).toFixed(2));
    },
  };
  return api;
}

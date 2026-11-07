// Example recording against the public TodoMVC demo (no sign-in needed).
// Copy next to kit.mjs in your project folder, then: node example-todomvc.mjs
// Needs out/todo-basics/audio/durations.json from tts.py first.
import { startRecording } from "./kit.mjs";

const BASE = process.env.APP_URL ?? "https://demo.playwright.dev/todomvc/";
const r = await startRecording({ name: "todo-basics", viewport: { width: 1440, height: 810 }, scale: 2, profile: "./profile-demo" });
const { page } = r;
page.setDefaultTimeout(6000); // one missing selector costs 6 s, not 30 s

await page.goto(BASE, { waitUntil: "domcontentloaded" });
// The persistent profile keeps app data between takes: start every take from a clean state.
await page.evaluate(() => localStorage.clear());
await page.reload({ waitUntil: "domcontentloaded" });
const input = page.getByPlaceholder("What needs to be done?");
await input.waitFor();
await page.mouse.move(720, 400);

await r.beat("b1", async () => {
  await r.pause(1);
  await r.moveTo(input);
});

await r.beat("b2", async () => {
  await r.click(input);
  for (const t of ["Write the script", "Record the demo", "Share the video"]) {
    await input.pressSequentially(t, { delay: 40 });
    await input.press("Enter");
    await r.pause(0.4);
  }
});

await r.beat("b3", async () => {
  await r.click(page.getByTestId("todo-item").first().getByRole("checkbox"));
});

await r.beat("b4", async () => {
  await r.click(page.getByRole("link", { name: "Active" }));
  await r.pause(1);
  await r.click(page.getByRole("link", { name: "Completed" }));
});

await r.beat("b5", async () => {
  await r.click(page.getByRole("link", { name: "All" }));
  await r.moveTo(page.getByRole("button", { name: "Clear completed" }));
});

await r.finish();

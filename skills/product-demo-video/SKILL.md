---
name: product-demo-video
description: Use when the user asks for a narrated demo video, product walkthrough video, or video tutorial of a real web app. Records the real app in headed Chrome (CDP screencast), adds a Kokoro AI voiceover, step labels and subtitles, and composites a 1080p mp4 with ffmpeg.
---

# Product demo video

Record the real app, never mock animations. Every video has:
- the app framed as a browser (or phone) on a soft cream background
- a step label at the top ("04 / 11 · Add a task")
- sentence-by-sentence subtitles
- an AI voiceover (Kokoro, runs locally, free)
- intro and outro title cards

Pipeline: **script -> voice -> recording timed to the voice -> composite -> check frames.**
A 2-minute video usually takes 30 to 60 minutes end to end, most of it tuning selectors in the recording script.

## Prerequisites (macOS)
| Need | Install |
|---|---|
| Google Chrome | regular install |
| Node 20+ | `brew install node` |
| ffmpeg | `brew install ffmpeg` |
| uv (Python env manager) | `brew install uv` |

The compositor uses macOS system fonts (Georgia, Helvetica Neue). On Linux, change `SERIF` and `SANS` in `kit/compose.py`.

Kokoro voice environment, built once and reused (set `KOKORO_VENV` to wherever you like):
```
export KOKORO_VENV=~/.local/share/product-demo-video/kokoro-env
uv venv -p 3.12 "$KOKORO_VENV"
uv pip install -p "$KOKORO_VENV/bin/python" kokoro soundfile pillow espeakng-loader \
  "en_core_web_sm @ https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl"
```
The spaCy model is installed explicitly because its auto-download fails inside a venv. The first TTS run downloads the Kokoro model (about 330 MB) from Hugging Face.

## Ask the user up front
1. Who is the audience (customers, new teammates, investors)?
2. Voiceover plus subtitles, or subtitles only?
3. Which environment to record (a sandbox project, staging or local, never production data)?

## Kit (`kit/` next to this file)
| File | What it does |
|---|---|
| `login.mjs` | Opens headed Chrome on a persistent `./profile`. The USER signs in by hand; the script only waits for a signed-in signal. |
| `kit.mjs` | `startRecording({name, viewport, scale, profile})` returns `{page, beat, fastForward, moveTo, click, scrollTo, scrollBy, pause, finish}`. Injects a visible cursor, click ripple, a visible copy of `title` tooltips, and blurs email addresses. |
| `tts.py` | `script.json` -> `out/<name>/audio/<id>.wav` + `durations.json` (voice `af_heart`, 24 kHz). |
| `compose.py` | `out/<name>/{script,beats,capture}.json` + frames + audio -> `out/<name>/<name>-demo.mp4`. Brand text from env `DEMO_BRAND`. |
| `example-script.json`, `example-todomvc.mjs` | A worked example against the public TodoMVC demo app (no sign-in needed). |

Project setup (one folder per video series):
```
mkdir my-tutorials && cd my-tutorials
npm init -y && npm i playwright
cp <skill-dir>/kit/kit.mjs <skill-dir>/kit/login.mjs .
```
`kit.mjs` must sit in the project so `playwright` resolves. Run everything from the project folder.

## Steps
1. **Script first.** Write `out/<name>/script.json`: 6 to 12 beats, each `{id, label, say, caption?}`.
   - `say` is spoken; add `caption` when the screen text should differ (say "P R", caption "PR").
   - Every claim must be something you saw in the app or its help text. Never invent URLs, numbers or features. List anything the user should double-check.
   - No em dashes; short sentences read better aloud.
2. **Voice.** `$KOKORO_VENV/bin/python kit/tts.py out/<name>/script.json out/<name>/audio`. Play the user a short sample before the full run.
3. **Sign in.** `node login.mjs <app-url> "<selector only visible when signed in>"`, run in the background, and ask the user to sign in. Never type credentials. Reuse `./profile` for every recording; only one Chrome can hold it at a time.
4. **Record.** Write `<name>.mjs` (start from `example-todomvc.mjs`) and run `node <name>.mjs`.
   - Headed by default: headless screencast is 1x only. Headed gives 2x frames (1440x810 -> 2880x1620).
   - `beat(id, fn)` runs the actions, then holds until that beat's narration (+0.6 s) has finished.
   - `fastForward(label, fn)` for long waits (an agent thinking, a build): compressed to 3 s with a "fast-forward" chip.
   - Move the mouse away before scrolling so hover tooltips don't linger.
   - Prefer stable selectors (roles, labels, fixed text), because AI-generated content changes between takes.
   - Never use Playwright's `recordVideo`: it records at CSS pixels and pads the frame.
5. **Composite.** `DEMO_BRAND="My App" $KOKORO_VENV/bin/python kit/compose.py <name> desktop "<title>" "<subtitle>" "<outro tagline>"`.
   - Always run ffmpeg with `-nostdin`.
   - Never build alpha-channel intermediates with looped masks (one grew to 44 GB); the kit uses a PNG ring overlay instead.
6. **Check before sharing.** Pull frames at several timestamps (`ffmpeg -ss 30 -i out/<name>/<name>-demo.mp4 -frames:v 1 check.png`) and look at them: labels in sync, subtitles not covering the UI, no personal data, no stray tooltips. Ask before opening files for the user.

## Gotchas
- Pages that never reach `networkidle` (GitHub, apps with live sockets): use `domcontentloaded`, then wait for a known text with `state: "attached"`.
- `page.setDefaultTimeout(6000)` so one missing selector costs 6 s instead of 30 s.
- Forms may keep a draft between takes: clear inputs with `fill("")` before typing. A "Discard" button may open a confirm dialog.
- `kit.mjs` holds the last frame until `finish()` and repeats the final ffconcat entry; without both, a static ending turns grey.
- Updating a video after a UI change = fix the selectors, re-run the recording and compose. The script and voice are reused.

## Rules
- Record in a sandbox, staging or local environment with sample data, never production customer data.
- Don't submit forms that send invites, emails or payments: hover instead of clicking.
- Restore any settings you change during a take.
- At the end, report every side effect (for example "created 3 sample records in the demo project").

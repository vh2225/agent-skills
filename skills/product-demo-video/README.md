# product-demo-video

A Claude Code skill that makes narrated tutorial videos of a real web app. It records the app in Chrome, adds a local AI voiceover (Kokoro), step labels and subtitles, and renders a 1080p mp4 with ffmpeg.

## Install
```
mkdir -p ~/.claude/skills
cp -R skills/product-demo-video ~/.claude/skills/
```
Then install the prerequisites in `SKILL.md` (Chrome, Node, ffmpeg, uv) and build the Kokoro environment once. In a new Claude Code session the skill loads when you ask for a demo or tutorial video, or with `/product-demo-video`.

## First video
In an empty folder, open Claude Code and paste:

> Use the product-demo-video skill to make a 60-second narrated tutorial of `<your app URL>`, recorded in a sandbox or staging environment. Audience: new users. Write the script first and show it to me, play me a voice sample, then open Chrome so I can sign in myself. Only describe what you actually see in the app, use sample data, don't send invites or emails, and show me a few frames before the final render.

To try the pipeline without your own app, ask it to run the included TodoMVC example.

## Inside
- `SKILL.md`: the workflow the agent follows.
- `kit/`: recorder (`kit.mjs`), manual sign-in helper (`login.mjs`), voice (`tts.py`), compositor (`compose.py`), and a TodoMVC example.

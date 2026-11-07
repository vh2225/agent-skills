# Usage: $KOKORO_VENV/bin/python tts.py script.json outdir [voice]
# script.json: [{"id": "...", "say": "..."}]; writes outdir/<id>.wav and outdir/durations.json
import json, sys, os
if "ESPEAK_DATA_PATH" not in os.environ:
    import espeakng_loader; os.environ["ESPEAK_DATA_PATH"] = espeakng_loader.get_data_path()
import numpy as np, soundfile as sf
from kokoro import KPipeline
beats = json.load(open(sys.argv[1])); out = sys.argv[2]; voice = sys.argv[3] if len(sys.argv) > 3 else "af_heart"
os.makedirs(out, exist_ok=True)
pipe = KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M")
durs = {}
for b in beats:
    if not b.get("say"): continue
    audio = np.concatenate([np.asarray(a) for _, _, a in pipe(b["say"], voice=voice, speed=1.0)])
    sf.write(f"{out}/{b['id']}.wav", audio, 24000)
    durs[b["id"]] = round(len(audio) / 24000, 3)
    print(b["id"], durs[b["id"]], flush=True)
json.dump(durs, open(f"{out}/durations.json", "w"), indent=1)

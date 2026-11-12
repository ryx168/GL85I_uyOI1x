# AI 日报 — news-broadcast video, rendered on GitHub Actions

A 新闻联播-style "AI Daily" episode (1920×1080, ~2 min 48 s) generated entirely from code:

- `tpl/index.tpl.html` — the [HyperFrames](https://hyperframes.heygen.com) composition: 9 scenes,
  GSAP animation, top-left segment tag, bilingual lower-thirds, scrolling 快讯 ticker.
- `build.py` — the bilingual script. Synthesizes every sentence with
  [edge-tts](https://github.com/rany2/edge-tts) (zh-CN-YunyangNeural for the anchor,
  zh-CN-XiaoxiaoNeural for 快讯), measures each clip, lays scenes out on the timeline and
  writes `index.html`. The mp3 cache under `assets/vo/cache/` is committed so the build also works
  without reaching Microsoft's TTS endpoint.
- `.github/workflows/render.yml` — every push to `main` (or *Run workflow*) builds, lints, renders
  and publishes `ai-daily.mp4` + a contact sheet as a Release `run-<n>` and as artifacts.

Lead story: Autor et al., *Does AI Assistance Enhance or Erode Expertise?*, NBER Working Paper 35720.

## Local

```
python -m pip install -U edge-tts
python build.py
npx --yes hyperframes@0.5.1 lint
npx --yes hyperframes@0.5.1 render --quality draft --output renders/draft.mp4
```

Edit the script in `build.py` (text pairs = narration + caption), re-run `build.py`, push.

# 🎬 Academic Group Conference Video Generator

A polished MP4 highlight reel for your group's conference — generated from one config file. ~10 min of typing, then `python3 video_generator.py`.

---

## Quick start

```bash
# 1. Install
pip install pillow opencv-python numpy qrcode
brew install ffmpeg          # or: apt install ffmpeg / winget install ffmpeg

# 2. Edit config.json (your conf, presenters, lab info — see WORKFLOW.md)

# 3. First run: creates submission folders + the music
python3 video_generator.py

# 4. Share the submissions/ folders, ask each presenter for video.mp4 + photo.jpg

# 5. Final render
python3 video_generator.py
```

Output: **`output_video.mp4`** — 1280×720, with cross-fades and music.

> **Read [WORKFLOW.md](WORKFLOW.md) first** — it's the 1-page fill-in sheet with the JSON template, the email template for your team, and a troubleshooting table. Don't bother reading the rest of this file unless WORKFLOW.md doesn't cover what you need.

---

## What you get

| Slide | Content |
|---|---|
| **Intro** | Conference name, acronym, date |
| **Per presenter** | Title · authors · project clip · headshot · caption · sponsor logos |
| **Outro** | Lab name, PI, members, QR code |

Background music is procedural (synthesised in-script, MIT-licensed). Pick a style in `config.json`:

```json
"music": { "style": "jazz" }   // or "house" — see WORKFLOW.md
```

---

## Common fixes

| Problem | Fix |
|---|---|
| `ModuleNotFoundError` | `pip install pillow opencv-python numpy qrcode` |
| No audio in output | Install ffmpeg |
| Custom config / output path | `python3 video_generator.py my_config.json out.mp4` |
| Different colour, resolution, fade length, etc. | See the comments at the top of `video_generator.py` |

---

## License

MIT. Free to use, modify, and share. A ⭐ if it saved you time is appreciated.

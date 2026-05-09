# Conference Video — PI Quick Sheet

**Total time: ~10 min of typing + one email to your team.**

```
1.  Edit config.json   (one form, see template below)
2.  python3 video_generator.py     ← creates upload folders
3.  Email your team    (template below) and wait for files
4.  python3 video_generator.py     ← renders output_video.mp4
```

That's it. Skip everything else on this page unless something breaks.

---

## Before you start (30 sec preflight)

- [ ] Python 3.10+ and `ffmpeg` installed *(`brew install ffmpeg` on Mac)*
- [ ] One folder where everyone can upload (Google Drive, Dropbox, your shared server) — pick now, you'll share it in step 3
- [ ] List of presenters with their paper titles handy

You do **not** need: presenter videos, photos, sponsor logos, or music yet. The script collects those after you fill in the config.

---

## Step 1 — Fill in `config.json`

Open `config.json` and replace the placeholder values. **Only the fields marked ★ are required.** Everything else can stay as-is.

```jsonc
{
  "qr_url": "https://your-lab.edu",          // ★ link the QR code points to

  "conference": {
    "name":    "Full Conference Name",       // ★ "International Conference on …"
    "acronym": "CONF 2025",                  // ★ "ICRA 2025"
    "date":    "May 19–23, 2025  •  City"    // ★ free text, any format
  },

  "presentations": [
    {
      "title":   "Paper title here",         // ★
      "authors": "A. Smith, B. Jones et al.",// ★
      "presenter": {
        "name": "Ada Smith",                 // ★ used to name the upload folder
        "role": "phd"                        // ★ "phd" or "postdoc" — picks the subfolder
      },
      "caption":       "One-line result",    //   optional, shown under video
      "funding_logos": ["NSF", "NIH"]        //   optional, see list below
    }
    // duplicate the {…} block above for each presenter, separated by commas
  ],

  "group": {
    "name":    "Your Lab Name",              // ★
    "pi":      "Prof. Your Name, Ph.D.",     // ★
    "members": ["Ada Smith (Ph.D.)",
                "Bob Jones (Postdoc)"],      //   optional, shown on outro slide
    "website": "https://yourlab.edu"
  }
}
```

**Funding logo names** *(case-insensitive, built-in coloured badges):*
`NSF · NIH · DARPA · DOE · NASA · NSERC · EU · ERC · EPSRC · ANR · OXFORD · CAMBRIDGE · MIT · STANFORD · ETH`

For anything else, drop a transparent PNG in `assets/sponsors/` named after the key (e.g. `MYAGENCY.png`) and use `"funding_logos": ["MYAGENCY"]`.

> **Don't touch** the `theme` and `music` blocks unless you specifically want a different colour or soundtrack. Defaults look fine.

---

## Step 2 — Create the upload folders

```bash
python3 video_generator.py
```

The first run reads your config and creates one folder per presenter under `submissions/`, e.g.:

```
submissions/phds/ada_smith/
submissions/postdocs/bob_jones/
```

Each folder has a `README.txt` telling the presenter what to drop in.

---

## Step 3 — Email your presenters (copy-paste template)

> Subject: 5 seconds of footage for our [CONF 2025] highlight reel
>
> Hi all,
>
> I'm putting together our group's conference highlight reel. **Please upload two files** to your folder by **[deadline]**:
>
> 1. **A short demo video** — 5–10 seconds, any format (mp4/mov/avi). Screen recording, lab footage, or animation. No need for narration; it'll be set to background music.
> 2. **A headshot photo** — jpg or png, anything reasonably recent. A simple selfie is fine.
>
> Your upload folder: **[paste your shared link here]/[role]s/[firstname_lastname]/**
>
> Filenames don't matter — just make sure one file is the video and one is the photo.
>
> Thanks!

---

## Step 4 — Render the final video

Once everyone has uploaded:

```bash
python3 video_generator.py
```

Output: **`output_video.mp4`** (1280×720, with cross-fades and background music).

If a presenter is missing files, the script tells you which folder is empty and skips them gracefully — you can re-run later when they come through.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError` | `pip install pillow opencv-python numpy qrcode` |
| Output has no audio | Install ffmpeg (`brew install ffmpeg` / `apt install ffmpeg`) and re-run |
| Presenter's video is too long | Set `"duration": 5` (or any 5–10) on that presenter's block |
| Wrong folder name for a presenter | Add `"folder": "custom_name"` inside `"presenter": {...}` |
| Want a different colour scheme | Add `"theme": {"accent_color": "#FF5722"}` — see README.md for full options |
| Music too loud / quiet | Edit `"music": {"volume": 0.22}` (0 = silent, 1 = max) |
| Want a different vibe | Edit `"music": {"style": "house"}` → `"jazz"` for peaceful jazz with a subtle techno pulse. Both are generated in-script, no licensing concerns. |
| Need 1080p instead of 720p | Edit `WIDTH, HEIGHT = 1920, 1080` at the top of `video_generator.py` |

For anything deeper (custom layouts, batch runs, theming details), see [README.md](README.md).

# 🎬 Academic Group Conference Video Generator

Automatically assembles a polished MP4 highlight reel for your research group's conference presentations — from a single config file.

> **All names, titles, and institutions in `config.json` are fictional placeholders.**  
> Replace them with your real group data before use.

![layout](https://img.shields.io/badge/layout-1280×720_HD-blue)
![python](https://img.shields.io/badge/python-3.10+-green)
![license](https://img.shields.io/badge/license-MIT-orange)

---

## What it produces

| Slide | Content |
|---|---|
| **Intro** | Conference name, acronym, date |
| **Per presenter** | Paper title + authors · project video (left) · headshot photo (right) · caption · sponsor logos |
| **Outro** | Group name, PI, members, QR code, "Thank you" |

Background music is mixed in automatically — pick `"house"` (driving house/techno) or `"jazz"` (peaceful jazz with a subtle techno pulse) in `config.json`, or drop your own track in `assets/music/`.  
Cross-fades connect every slide.

---

## Quick start

```bash
# 1. Install dependencies
pip install pillow opencv-python numpy qrcode

# 2. Fill in config.json — see WORKFLOW.md for the minimal fields

# 3. First run: creates submission folders + generates music
python3 video_generator.py

# 4. Share submissions/ with presenters so they can upload video.mp4 + photo.jpg

# 5. Final render once all files are uploaded
python3 video_generator.py

# Output: output_video.mp4
```

> **ffmpeg** is used for audio mixing. Install with your system package manager  
> (`brew install ffmpeg` / `apt install ffmpeg`). Without it the video is rendered silently.

---

## Minimum config (just the required fields)

Open `config.json` and fill in these fields — everything else has sensible defaults:

```json
{
  "qr_url": "https://your-lab.edu",
  "conference": {
    "name":    "Full Conference Name",
    "acronym": "CONF 2025",
    "date":    "May 19–23, 2025  •  City, Country"
  },
  "presentations": [
    {
      "title":   "Paper title",
      "authors": "A. Smith, B. Jones et al.",
      "presenter": { "name": "Ada Smith", "role": "phd" }
    }
  ],
  "group": {
    "name": "Your Lab Name",
    "pi":   "Prof. Your Name, Ph.D.",
    "members": ["Ada Smith (Ph.D.)", "Bob Jones (Postdoc)"]
  }
}
```

See `WORKFLOW.md` for a simple fill-in-the-blanks planning sheet.

---

## Installation

**Python 3.10+** required.

```bash
pip install pillow opencv-python numpy qrcode
```

Optional (for audio):

```bash
# macOS
brew install ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg

# Windows
winget install ffmpeg
```

---

## Folder structure

```
your-project/
├── video_generator.py      ← main script
├── config.json             ← all your data goes here
├── WORKFLOW.md             ← quick fill-in sheet for the PI
├── README.md               ← this file
│
├── assets/
│   ├── music/
│   │   └── background.wav  ← auto-generated house/lofi beat; replace freely
│   └── sponsors/
│       ├── NSF.png         ← logo PNGs named after the key in config.json
│       ├── NIH.png
│       └── …
│
└── submissions/
    ├── phds/
    │   └── ada_smith/          ← one folder per PhD student
    │       ├── README.txt      ← auto-generated upload instructions
    │       ├── video.mp4       ← 5–10 s project demo clip
    │       └── photo.jpg       ← headshot photo
    └── postdocs/
        └── bob_jones/
            ├── README.txt
            ├── video.mp4
            └── photo.jpg
```

All folders are **created automatically** on the first run of `video_generator.py`.

---

## Full `config.json` reference

### Top-level keys

```json
{
  "qr_url":        "https://your-lab.edu",
  "music":         { "path": "", "volume": 0.22 },
  "theme":         { … },
  "conference":    { … },
  "presentations": [ … ],
  "group":         { … }
}
```

---

### `conference`

```json
"conference": {
  "name":     "Full name of the conference",
  "acronym":  "SHORT 2025",
  "date":     "Month DD–DD, YYYY  •  City, Country",
  "duration": 5
}
```

| Key | Description |
|---|---|
| `name` | Full conference name (wrapped automatically) |
| `acronym` | Short ID shown above the title on the intro slide |
| `date` | Free-text date + location string |
| `duration` | Intro slide duration in seconds (default 5) |

---

### `presentations` (one object per presenter)

```json
{
  "title":    "Full paper or project title",
  "authors":  "A. Smith, B. Jones et al.",
  "caption":  "One-liner shown below the project video",
  "duration": 7,
  "presenter": {
    "name": "Ada Smith",
    "role": "phd"
  },
  "funding_logos": ["NSF", "NIH", "DARPA"]
}
```

| Key | Required | Description |
|---|---|---|
| `title` | ★ | Paper / project title (wrapped automatically) |
| `authors` | ★ | Author string |
| `presenter.name` | ★ | Full name — used to derive the submission folder |
| `presenter.role` | ★ | `"phd"` or `"postdoc"` — determines which subfolder |
| `caption` | optional | Short result sentence shown below the video area |
| `duration` | optional | Slide duration in seconds (default 7, range 5–10) |
| `presenter.folder` | optional | Override the auto-derived `firstname_lastname` folder name |
| `funding_logos` | optional | List of agency keys or file paths |

**Submission folder auto-derivation:**  
`Ada Smith` with role `phd` → `submissions/phds/ada_smith/`

---

### `group` (outro slide)

```json
"group": {
  "name":    "Your Lab Name",
  "pi":      "Prof. Your Name, Ph.D.",
  "members": ["Ada Smith (Ph.D.)", "Bob Jones (Postdoc)", "…"],
  "website": "https://yourlab.edu",
  "duration": 8
}
```

---

### `theme` (optional — remove the whole block for default black/gold)

```json
"theme": {
  "background_color": "#000000",
  "background_image": "",
  "accent_color":     "#FFB800",
  "title_color":      "#FFFFFF",
  "text_color":       "#C8CDD7",
  "secondary_color":  "#6E7684"
}
```

| Key | Default | Description |
|---|---|---|
| `background_color` | `#000000` (black) | Solid background colour |
| `background_image` | *(none)* | Relative path to a JPG/PNG; overrides `background_color` |
| `accent_color` | `#FFB800` (gold) | Highlight bars, accent text, logo strips |
| `title_color` | `#FFFFFF` | Paper title and main headings |
| `text_color` | `#C8CDD7` | Body text (authors, captions) |
| `secondary_color` | `#6E7684` | Dim labels and secondary info |

---

### `music`

```json
"music": {
  "path":   "",
  "volume": 0.22
}
```

| Key | Description |
|---|---|
| `path` | Path to a WAV/MP3 file. Leave empty to auto-generate a house/lofi beat. |
| `volume` | Mix volume 0–1 (0.22 = quiet background) |

---

## Sponsor logos

Place logo image files in `assets/sponsors/`, named after the key used in `config.json`:

```
assets/sponsors/
  NSF.png
  NIH.jpg
  OXFORD.png
  RADlab.png
```

Matching is **case-insensitive**. Transparent PNGs work best.  
If no file is found, a coloured placeholder badge is generated automatically.

Pre-coloured badges are built in for: `NSF`, `NIH`, `DARPA`, `DOE`, `NASA`, `NSERC`,  
`EU`, `ERC`, `EPSRC`, `ANR`, `ROBOSOFT`, `OXFORD`, `CAMBRIDGE`, `MIT`, `STANFORD`, `ETH`, `RADLAB`.

---

## Collecting files from presenters

1. Run `python3 video_generator.py` once — this creates `submissions/` folders with a `README.txt` for each presenter.
2. Share the folder (Google Drive, OneDrive, your shared server …) with the relevant person.
3. Ask them to upload:
   - **`video.mp4`** — 5–10 second project demo (screen recording, lab footage, animation …)
   - **`photo.jpg`** — headshot
4. Once all folders are filled, run the script again to generate the final video.

---

## Background music

Two procedural styles ship in the script — both synthesised from sine waves and noise, so the output is **100% original audio, MIT-licensed, free to use anywhere**:

| `"style"` | Sound |
|---|---|
| `"house"` *(default)* | Driving house/techno: 4-on-the-floor kick, snare on 2 & 4, syncopated Am7 bass, chord pad. 110 BPM. |
| `"jazz"` | Peaceful jazz with a subtle techno pulse: brushed drums + quiet kick, walking upright bass, warm maj7/9 pad, sparse sax-like lead. Dm7 → G7 → Cmaj7 → Am7 vamp at 88 BPM. |

Set the style in `config.json`:

```json
"music": { "style": "jazz", "volume": 0.22 }
```

- The track is regenerated each run to match the video length.
- To use your own track, drop any WAV/MP3 in `assets/music/` (the script picks the first audio file it finds) or set `"music": {"path": "assets/music/mytrack.mp3"}`.
- Volume is controlled by `"volume"` in `config.json` (default `0.22`, i.e. quiet background).

Good sources of CC-licensed music:
- [freemusicarchive.org](https://freemusicarchive.org)
- [ccmixter.org](https://ccmixter.org)
- [freesound.org](https://freesound.org)

---

## Running the script

```bash
# Default: reads config.json, writes output_video.mp4
python3 video_generator.py

# Custom config file
python3 video_generator.py my_config.json

# Custom config + output path
python3 video_generator.py my_config.json icra_2025_reel.mp4
```

---

## Customisation

| What | Where |
|---|---|
| Resolution | `WIDTH, HEIGHT = 1280, 720` at top of `video_generator.py` (change to `1920, 1080` for full HD) |
| Accent colour | `"theme": {"accent_color": "#FFB800"}` in `config.json` |
| Background | `"theme": {"background_color": "#1a1a2e"}` or `"background_image": "bg.jpg"` |
| Slide duration | `"duration"` per presentation in `config.json` |
| Music volume | `"music": {"volume": 0.22}` in `config.json` |
| Fade length | `FADE_FRAMES = 12` in `video_generator.py` |

---

## Slide layout reference

```
┌─────────────────────────────────────────────────────┬──────────────┐
│ Paper title                                  1 / 3  │              │
│ Authors                                             │  [ photo ]   │
├─────────────────────────────────────────────────────│  centred     │
│                                                     │              │
│           Project video (5-10 s clip)               ├──────────────│
│                                                     │ Presenter:   │
│                                                     │ Ada Smith    │
├─────────────────────────────────────────────────────┴──────────────┤
│ Caption text below video                                           │
│ Supported by:  [NSF]  [NIH]  [DARPA]                              │
└────────────────────────────────────────────────────────────────────┘
```

---

## Dependencies

| Package | Purpose |
|---|---|
| `pillow` | Drawing text, overlays, logos |
| `opencv-python` | Video reading & writing |
| `numpy` | Fast frame compositing |
| `qrcode` | QR code generation |
| `ffmpeg` *(system)* | Audio mixing |

---

## License

MIT — free to use, modify, and share.  
If you publish a video made with this tool, a mention or star ⭐ is appreciated but not required.

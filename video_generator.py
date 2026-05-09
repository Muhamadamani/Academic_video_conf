#!/usr/bin/env python3
"""
Academic Group Conference Video Generator — MVP v5
===================================================
Generates an MP4 highlight reel from a JSON config file.

Slide layout (matches reference screenshot):
  • Themed background (solid colour or image)
  • Top-left  : paper title + authors
  • Left 74 % : presenter's 5-second project video
  • Right col : rectangular presenter photo (vertically centred) + name
  • Bottom    : caption text + funding logos / badges
  • Intro     : conference name, acronym, date
  • Outro     : group name, PI, members, QR code
  • Music     : procedural backing track auto-generated; pick "house"
                or "jazz" via config.json["music"]["style"]. Replace freely.

All colours, the background, and text colours are configurable via
the "theme" block in config.json.

Usage:
    python3 video_generator.py                       # uses config.json
    python3 video_generator.py config.json out.mp4
"""

import json, os, subprocess, sys, textwrap, wave
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import qrcode
from PIL import Image, ImageDraw, ImageFont

# ── Resolution & timing ───────────────────────────────────────────────────────
WIDTH, HEIGHT = 1280, 720
FPS           = 30
FADE_FRAMES   = 12

# ── Default colour palette (overridden by config "theme") ─────────────────────
_DEF_ACCENT    = (255, 184,   0)   # gold
_DEF_TITLE     = (255, 255, 255)   # white
_DEF_TEXT      = (200, 205, 215)   # light grey
_DEF_SECONDARY = (110, 118, 132)   # dim grey
_DEF_BG        = (  0,   0,   0)   # black

# ── Layout constants ──────────────────────────────────────────────────────────
MARGIN    = 22
TITLE_Y   = 16
VIDEO_X   = MARGIN
VIDEO_Y   = 106
VIDEO_W   = 938
VIDEO_H   = 490
RIGHT_X   = VIDEO_X + VIDEO_W + 16   # 976
RIGHT_W   = WIDTH - RIGHT_X - MARGIN  # 282
PHOTO_H   = 188
PHOTO_Y   = (HEIGHT - PHOTO_H) // 2   # vertically centred
CAPTION_Y = VIDEO_Y + VIDEO_H + 6
LOGO_Y    = CAPTION_Y + 30

# ── Built-in badge colours ────────────────────────────────────────────────────
_BADGE_COLOURS: dict[str, tuple] = {
    "NSF": (0, 95, 173), "NIH": (32, 84, 138), "DARPA": (169, 29, 58),
    "DOE": (0, 102, 51), "NASA": (252, 61, 33), "NSERC": (0, 76, 145),
    "EU": (0, 51, 153),  "ERC": (0, 70, 127),  "EPSRC": (34, 34, 140),
    "ANR": (255, 80, 0), "ROBOSOFT": (180, 30, 30), "OXFORD": (0, 33, 71),
    "CAMBRIDGE": (163, 31, 52), "MIT": (163, 31, 52),
    "STANFORD": (140, 21, 21),  "ETH": (30, 100, 170),
    "RADLAB": (30, 100, 180),
}

# ── Font helpers ──────────────────────────────────────────────────────────────
_FONT_DIR = "/usr/share/fonts/truetype/google-fonts"
_FALL     = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
_FALL_B   = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"

def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(os.path.join(_FONT_DIR, name), size)
    except IOError:
        return ImageFont.truetype(_FALL_B if "Bold" in name else _FALL, size)


# ════════════════════════════════════════════════════════════════════════════════
# Theme loader
# ════════════════════════════════════════════════════════════════════════════════

def _hex(s: str, default: tuple) -> tuple:
    """Parse '#RRGGBB' or 'RRGGBB' → (R, G, B). Returns default on failure."""
    if not s:
        return default
    s = s.lstrip("#")
    try:
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
    except Exception:
        return default


def load_theme(config: dict, config_dir: Path) -> dict:
    """
    Read the optional 'theme' block and return a resolved theme dict:
      bg_pil      (R,G,B) tuple — PIL background colour
      bg_frame    (H,W,3) BGR numpy — background image or solid colour frame
      has_bg_img  bool
      accent      (R,G,B)
      title       (R,G,B)
      text        (R,G,B)
      secondary   (R,G,B)
    """
    raw = config.get("theme", {})

    bg_color  = _hex(raw.get("background_color", ""), _DEF_BG)
    accent    = _hex(raw.get("accent_color",     ""), _DEF_ACCENT)
    title_c   = _hex(raw.get("title_color",      ""), _DEF_TITLE)
    text_c    = _hex(raw.get("text_color",       ""), _DEF_TEXT)
    second_c  = _hex(raw.get("secondary_color",  ""), _DEF_SECONDARY)

    # Background image
    bg_img_rel = raw.get("background_image", "").strip()
    has_img    = False
    bg_frame   = np.full((HEIGHT, WIDTH, 3), bg_color[::-1], dtype=np.uint8)  # BGR

    if bg_img_rel:
        bg_img_path = config_dir / bg_img_rel
        if bg_img_path.exists():
            img_cv = cv2.imread(str(bg_img_path))
            if img_cv is not None:
                bg_frame = cv2.resize(img_cv, (WIDTH, HEIGHT))
                has_img  = True
            else:
                print(f"  WARNING: could not load background image: {bg_img_path}")
        else:
            print(f"  WARNING: background image not found: {bg_img_path}")

    return {
        "bg_pil"    : bg_color,
        "bg_frame"  : bg_frame,
        "has_bg_img": has_img,
        "accent"    : accent,
        "title"     : title_c,
        "text"      : text_c,
        "secondary" : second_c,
    }


def _bg_pil(theme: dict) -> Image.Image:
    """Return a fresh PIL RGB canvas with the themed background."""
    if theme["has_bg_img"]:
        return Image.fromarray(cv2.cvtColor(theme["bg_frame"], cv2.COLOR_BGR2RGB))
    return Image.new("RGB", (WIDTH, HEIGHT), theme["bg_pil"])


# ════════════════════════════════════════════════════════════════════════════════
# House / lofi music generator
# ════════════════════════════════════════════════════════════════════════════════

def generate_house_music(duration_s: float, output_path: str,
                         sample_rate: int = 44100, bpm: int = 110) -> None:
    """
    Generate a smooth house / lofi-house background track and save as mono WAV.
    Pattern: 4/4 at 110 BPM — kick on every beat, snare on 2 & 4,
    8th-note hi-hats, syncopated Am7 bass, Am7 chord pad.
    Replace the output file with any CC-licensed track for a different sound.
    """
    n      = int(sample_rate * duration_s)
    audio  = np.zeros(n, dtype=np.float32)
    beat_n = int(sample_rate * 60.0 / bpm)    # samples per beat
    bar_n  = 4 * beat_n                         # samples per bar (4/4)
    s16    = beat_n // 4                        # 16th-note grid

    rng = np.random.default_rng(42)

    # ── Drum voices ────────────────────────────────────────────────────────────

    def kick(dur_s=0.22):
        d = int(dur_s * sample_rate)
        t = np.arange(d, dtype=np.float32) / sample_rate
        freq = 140 * np.exp(-t * 28) + 45        # pitch sweep 140→45 Hz
        amp  = np.exp(-t * 14)
        phase = np.cumsum(2 * np.pi * freq / sample_rate)
        return 0.80 * np.sin(phase) * amp

    def snare(dur_s=0.10):
        d = int(dur_s * sample_rate)
        t = np.arange(d, dtype=np.float32) / sample_rate
        noise = rng.standard_normal(d).astype(np.float32)
        amp   = np.exp(-t * 28)
        tone  = 0.35 * np.sin(2 * np.pi * 210 * t)
        return 0.40 * (noise * 0.65 + tone) * amp

    def hat(open_=False):
        dur_s = 0.055 if open_ else 0.022
        d     = int(dur_s * sample_rate)
        t     = np.arange(d, dtype=np.float32) / sample_rate
        noise = rng.standard_normal(d).astype(np.float32)
        # Very simple hi-pass: first-difference
        noise[1:] -= 0.88 * noise[:-1]
        amp = np.exp(-t * (9 if open_ else 55))
        return 0.13 * noise * amp

    kick_buf  = kick()
    snare_buf = snare()
    hat_buf   = hat(False)
    ohat_buf  = hat(True)

    def place(buf, pos):
        end = min(pos + len(buf), n)
        if pos < n:
            audio[pos:end] += buf[:end - pos]

    # 16-step patterns (each step = 1 sixteenth note)
    kick_pat  = [1,0,0,0, 0,0,1,0, 1,0,0,0, 0,1,0,0]  # 4-on-the-floor + syncopation
    snare_pat = [0,0,0,0, 1,0,0,0, 0,0,0,0, 1,0,0,0]   # 2 and 4
    hat_pat   = [1,0,1,0, 1,0,1,0, 1,0,1,0, 1,0,1,0]   # 8th notes
    ohat_step = {6, 14}                                   # open hat accents

    for bar_start in range(0, n, bar_n):
        for i in range(16):
            pos = bar_start + i * s16
            if kick_pat[i]:  place(kick_buf,  pos)
            if snare_pat[i]: place(snare_buf, pos)
            if hat_pat[i]:
                if i in ohat_step:  place(ohat_buf, pos)
                else:               place(hat_buf,  pos)

    # ── Bass line (Am key, syncopated) ────────────────────────────────────────
    #  A2=110 Hz, E2=82.41, D2=73.42, G2=98
    bass_seq = [
        (0.0,  110.00, 1.0),   # A2 on beat 1
        (1.5,   82.41, 0.75),  # E2 on the-and-of-2
        (2.0,   73.42, 0.85),  # D2 on beat 3
        (3.75,  98.00, 0.60),  # G2 pickup into next bar
    ]
    for bar_start in range(0, n, bar_n):
        for beat_off, freq, vel in bass_seq:
            pos = bar_start + int(beat_off * beat_n)
            if pos >= n:
                break
            dur = int(beat_n * 0.82)
            end = min(pos + dur, n)
            bt  = np.arange(end - pos, dtype=np.float32) / sample_rate
            # Slightly detune two oscillators for warmth
            osc = (0.70 * np.sin(2*np.pi * freq       * bt) +
                   0.20 * np.sin(2*np.pi * freq * 1.004 * bt) +
                   0.10 * np.sin(2*np.pi * freq * 2    * bt))
            amp = np.exp(-bt * 3.5) * (1 - np.exp(-bt * 40))  # fast attack, slow decay
            audio[pos:end] += (vel * 0.50 * osc * amp).astype(np.float32)

    # ── Chord pad (Am7 voicings, every 4 beats) ───────────────────────────────
    # Alternates Am7 → Am7/C for subtle movement
    voicings = [
        [220.00, 261.63, 329.63, 392.00],  # Am7  : A3 C4 E4 G4
        [220.00, 293.66, 349.23, 415.30],  # Am9-ish: A3 D4 F4 Ab4
    ]
    for vi, bar_start in enumerate(range(0, n, bar_n)):
        notes = voicings[vi % len(voicings)]
        dur   = min(bar_n, n - bar_start)
        ct    = np.arange(dur, dtype=np.float32) / sample_rate
        fade  = min(int(0.35 * sample_rate), dur // 4)
        env   = np.ones(dur, dtype=np.float32)
        env[:fade] = np.linspace(0.0, 1.0, fade)
        env[-fade:] = np.linspace(1.0, 0.0, fade)
        pad = np.zeros(dur, dtype=np.float32)
        for note in notes:
            vib = 1.0 + 0.0018 * np.sin(2*np.pi * 5.3 * ct)
            pad += 0.055 * np.sin(2*np.pi * note       * vib * ct)
            pad += 0.018 * np.sin(2*np.pi * note * 2   * vib * ct)
            pad += 0.008 * np.sin(2*np.pi * note * 0.5 * vib * ct)  # sub
        audio[bar_start:bar_start + dur] += (pad * env).astype(np.float32)

    # ── Master fade & normalise ────────────────────────────────────────────────
    fade_n = int(min(2.0, duration_s * 0.06) * sample_rate)
    audio[:fade_n]  *= np.linspace(0.0, 1.0, fade_n)
    audio[-fade_n:] *= np.linspace(1.0, 0.0, fade_n)
    mx = np.max(np.abs(audio))
    if mx > 0:
        audio *= 0.78 / mx

    pcm = (audio * 32767).clip(-32768, 32767).astype(np.int16)
    with wave.open(output_path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())
    print(f"  ♪ House track generated → {output_path}")


# ════════════════════════════════════════════════════════════════════════════════
# Peaceful jazz with a touch of techno
# ════════════════════════════════════════════════════════════════════════════════

def generate_jazz_techno_music(duration_s: float, output_path: str,
                               sample_rate: int = 44100, bpm: int = 88) -> None:
    """
    Peaceful jazz vamp with a subtle 4-on-the-floor techno pulse underneath.
    Mono WAV. Progression: Dm7 → G7 → Cmaj7 → Am7 (2 bars each), walking
    upright bass, brushed drums, warm maj7/9 pad, sparse sax-like lead.
    """
    n       = int(sample_rate * duration_s)
    audio   = np.zeros(n, dtype=np.float32)
    beat_n  = int(sample_rate * 60.0 / bpm)
    bar_n   = 4 * beat_n
    chord_n = 2 * bar_n            # two bars per chord
    s16     = beat_n // 4
    rng     = np.random.default_rng(7)

    # ── Drum voices (softer than the house kit) ────────────────────────────────

    def soft_kick(dur_s=0.20):
        d = int(dur_s * sample_rate)
        t = np.arange(d, dtype=np.float32) / sample_rate
        freq = 110 * np.exp(-t * 30) + 50
        amp  = np.exp(-t * 12)
        phase = np.cumsum(2 * np.pi * freq / sample_rate)
        return 0.32 * np.sin(phase) * amp

    def brushed(dur_s=0.18):
        d = int(dur_s * sample_rate)
        t = np.arange(d, dtype=np.float32) / sample_rate
        noise = rng.standard_normal(d).astype(np.float32)
        noise[1:] -= 0.6 * noise[:-1]                # gentle highpass
        amp = np.exp(-t * 14) * (1 - np.exp(-t * 60))
        return 0.18 * noise * amp

    def shaker(dur_s=0.06):
        d = int(dur_s * sample_rate)
        t = np.arange(d, dtype=np.float32) / sample_rate
        noise = rng.standard_normal(d).astype(np.float32)
        noise[1:] -= 0.92 * noise[:-1]
        amp = np.exp(-t * 50)
        return 0.07 * noise * amp

    kick_buf  = soft_kick()
    brush_buf = brushed()
    shak_buf  = shaker()

    def place(buf, pos):
        end = min(pos + len(buf), n)
        if pos < n:
            audio[pos:end] += buf[:end - pos]

    kick_pat  = [1,0,0,0, 1,0,0,0, 1,0,0,0, 1,0,0,0]   # quiet 4-on-the-floor (the techno pulse)
    brush_pat = [0,0,0,0, 1,0,0,0, 0,0,0,0, 1,0,0,0]   # snare on 2 & 4
    shak_pat  = [0,0,1,0, 0,0,1,0, 0,0,1,0, 0,0,1,0]   # offbeat 8ths

    for bar_start in range(0, n, bar_n):
        for i in range(16):
            pos = bar_start + i * s16
            if kick_pat[i]:  place(kick_buf,  pos)
            if brush_pat[i]: place(brush_buf, pos)
            if shak_pat[i]:  place(shak_buf,  pos)

    # ── Chord progression: Dm7 → G7 → Cmaj7 → Am7 ─────────────────────────────
    # Each tuple: (pad_voicing_hz, walking_bass_4_notes_per_bar_hz)
    chord_cycle = [
        ([293.66, 349.23, 440.00, 523.25],   # Dm7  : D4 F4 A4 C5
         [73.42, 110.00, 87.31, 73.42]),     # walk : D2 A2 F2 D2
        ([196.00, 246.94, 293.66, 349.23],   # G7   : G3 B3 D4 F4
         [98.00, 123.47, 73.42, 98.00]),     # walk : G2 B2 D2 G2
        ([261.63, 329.63, 392.00, 493.88],   # Cmaj7: C4 E4 G4 B4
         [65.41,  98.00,  82.41, 65.41]),    # walk : C2 G2 E2 C2
        ([220.00, 261.63, 329.63, 392.00],   # Am7  : A3 C4 E4 G4
         [55.00,  82.41,  65.41, 55.00]),    # walk : A1 E2 C2 A1
    ]

    for ci, chord_start in enumerate(range(0, n, chord_n)):
        notes, walk = chord_cycle[ci % len(chord_cycle)]
        chord_dur   = min(chord_n, n - chord_start)

        # Pad
        ct   = np.arange(chord_dur, dtype=np.float32) / sample_rate
        fade = min(int(0.6 * sample_rate), chord_dur // 4)
        env  = np.ones(chord_dur, dtype=np.float32)
        if fade > 0:
            env[:fade]  = np.linspace(0.0, 1.0, fade)
            env[-fade:] = np.linspace(1.0, 0.0, fade)
        pad = np.zeros(chord_dur, dtype=np.float32)
        for note in notes:
            vib = 1.0 + 0.0014 * np.sin(2*np.pi * 4.7 * ct)
            pad += 0.045 * np.sin(2*np.pi * note       * vib * ct)
            pad += 0.012 * np.sin(2*np.pi * note * 2   * vib * ct)
            pad += 0.006 * np.sin(2*np.pi * note * 0.5 * vib * ct)
        audio[chord_start:chord_start + chord_dur] += (pad * env).astype(np.float32)

        # Walking bass — one note per beat over 2 bars (reuses the 4-note pattern)
        for bar in range(2):
            for beat in range(4):
                pos = chord_start + bar * bar_n + beat * beat_n
                if pos >= n:
                    break
                freq = walk[beat]
                dur  = int(beat_n * 0.78)
                end  = min(pos + dur, n)
                bt   = np.arange(end - pos, dtype=np.float32) / sample_rate
                osc  = (0.65 * np.sin(2*np.pi * freq         * bt) +
                        0.22 * np.sin(2*np.pi * freq * 1.005 * bt) +
                        0.13 * np.sin(2*np.pi * freq * 2     * bt))
                amp  = np.exp(-bt * 4.0) * (1 - np.exp(-bt * 50))
                audio[pos:end] += (0.42 * osc * amp).astype(np.float32)

    # ── Sparse sax-like lead (skips every 4th chord for breathing room) ───────
    lead_seq = [
        # (offset_in_beats, freq_hz, duration_in_beats, velocity)
        (0.5, 587.33, 1.5, 0.70),   # D5
        (3.0, 523.25, 1.0, 0.60),   # C5
        (5.5, 440.00, 1.5, 0.65),   # A4
    ]
    for ci, chord_start in enumerate(range(0, n, chord_n)):
        if ci % 4 == 3:
            continue
        for off_b, freq, dur_b, vel in lead_seq:
            pos = chord_start + int(off_b * beat_n)
            if pos >= n:
                break
            dur = int(dur_b * beat_n)
            end = min(pos + dur, n)
            lt  = np.arange(end - pos, dtype=np.float32) / sample_rate
            vib = 1.0 + 0.004 * np.sin(2*np.pi * 5.5 * lt)
            osc = (0.55 * np.sin(2*np.pi * freq     * vib * lt) +
                   0.20 * np.sin(2*np.pi * freq * 2 * vib * lt) +
                   0.10 * np.sin(2*np.pi * freq * 3 * vib * lt))
            atk = min(int(0.08 * sample_rate), max(1, len(lt) // 4))
            rel = min(int(0.30 * sample_rate), max(1, len(lt) // 3))
            amp = np.ones(len(lt), dtype=np.float32)
            amp[:atk]  = np.linspace(0.0, 1.0, atk)
            amp[-rel:] = np.linspace(1.0, 0.0, rel)
            audio[pos:end] += (vel * 0.16 * osc * amp).astype(np.float32)

    # ── Master fade & normalise ────────────────────────────────────────────────
    fade_n = int(min(2.0, duration_s * 0.06) * sample_rate)
    if fade_n > 0:
        audio[:fade_n]  *= np.linspace(0.0, 1.0, fade_n)
        audio[-fade_n:] *= np.linspace(1.0, 0.0, fade_n)
    mx = np.max(np.abs(audio))
    if mx > 0:
        audio *= 0.75 / mx

    pcm = (audio * 32767).clip(-32768, 32767).astype(np.int16)
    with wave.open(output_path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())
    print(f"  ♪ Jazz-techno track generated → {output_path}")


# ════════════════════════════════════════════════════════════════════════════════
# Music style dispatcher
# ════════════════════════════════════════════════════════════════════════════════

def generate_music(style: str, duration_s: float, output_path: str) -> None:
    """Generate a procedural backing track in the requested style.

    Both styles are 100% original — synthesised from sine waves and noise
    in this script — so the output is free to use, modify, and redistribute
    under the project's MIT license. No third-party licensing required.
    """
    key = (style or "house").strip().lower().replace("-", "_").replace(" ", "_")
    if key in ("jazz", "jazz_techno", "peaceful", "peaceful_jazz"):
        generate_jazz_techno_music(duration_s, output_path)
    else:
        generate_house_music(duration_s, output_path)


# ════════════════════════════════════════════════════════════════════════════════
# Audio mixing (ffmpeg)
# ════════════════════════════════════════════════════════════════════════════════

def mix_audio(video_path: str, music_path: str, output_path: str,
              duration_s: float, volume: float = 0.22) -> bool:
    fade_s  = min(2.5, duration_s * 0.08)
    fade_st = max(0.0, duration_s - fade_s)
    filt = (
        f"[1:a]aloop=loop=-1:size=2000000000,"
        f"atrim=duration={duration_s:.2f},"
        f"afade=t=in:st=0:d=1.5,"
        f"afade=t=out:st={fade_st:.2f}:d={fade_s:.2f},"
        f"volume={volume}[aout]"
    )
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-i", video_path, "-i", music_path,
           "-filter_complex", filt,
           "-map", "0:v", "-map", "[aout]",
           "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
           output_path]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=90)
        if r.returncode == 0:
            return True
        print(f"  WARNING ffmpeg: {r.stderr.decode()[:200]}")
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        print(f"  WARNING: ffmpeg unavailable ({e}) — video will be silent.")
    return False


# ════════════════════════════════════════════════════════════════════════════════
# Asset / submission folder management
# ════════════════════════════════════════════════════════════════════════════════

VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}
PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def _folder_name(presenter: dict) -> str:
    if presenter.get("folder"):
        return presenter["folder"]
    return "_".join(presenter.get("name", "unknown").lower().split())


def _sub_folder(fl: str, role: str, config_dir: Path) -> Path:
    r = role if role.endswith("s") else role + "s"
    return config_dir / "submissions" / r / fl


def _find_file(folder: Path, exts: set) -> Optional[str]:
    if not folder.exists():
        return None
    for f in sorted(folder.iterdir()):
        if f.suffix.lower() in exts:
            return str(f)
    return None


def _write_if_new(path: Path, text: str) -> None:
    if not path.exists():
        path.write_text(text)


def create_asset_folders(config: dict, config_dir: Path) -> None:
    (config_dir / "assets" / "music").mkdir(parents=True, exist_ok=True)
    (config_dir / "assets" / "sponsors").mkdir(parents=True, exist_ok=True)
    _write_if_new(config_dir / "assets" / "music" / "README.txt",
        "Background music\n"
        "=================\n"
        "Drop any WAV, MP3, AAC, OGG or FLAC here.\n"
        "The script picks the first audio file it finds.\n\n"
        "Leave the folder empty to auto-generate a track. Pick a style in\n"
        "config.json:\n"
        '  "music": { "style": "house" }   ← driving house/techno (default)\n'
        '  "music": { "style": "jazz"  }   ← peaceful jazz with a techno pulse\n\n'
        "Both auto-generated styles are synthesised from scratch in this\n"
        "script — 100% original audio, MIT-licensed, free to use anywhere.\n\n"
        "Other CC-licensed music sources, if you want something custom:\n"
        "  freemusicarchive.org  ccmixter.org  freesound.org\n")
    _write_if_new(config_dir / "assets" / "sponsors" / "README.txt",
        "Sponsor logo images\n"
        "====================\n"
        "Place logo PNGs here, named after the key in config.json:\n"
        "  NSF.png   NIH.jpg   OXFORD.png   RADlab.png  …\n\n"
        "Matching is case-insensitive. Transparent PNGs look best.\n"
        "A coloured badge is generated automatically if no file is found.\n")
    for pres in config.get("presentations", []):
        p      = pres.get("presenter", {})
        fl     = _folder_name(p)
        role   = p.get("role", "phd")
        folder = _sub_folder(fl, role, config_dir)
        folder.mkdir(parents=True, exist_ok=True)
        _write_if_new(folder / "README.txt",
            f"Upload folder for: {p.get('name', fl)}  ({role})\n\n"
            "Please drop two files here (any filename, correct extension):\n"
            "  video.[mp4 | mov | avi]  — 5-10 s project demo clip\n"
            "  photo.[jpg | png]        — headshot\n")
    print("  assets/music/  assets/sponsors/")
    for pres in config.get("presentations", []):
        p = pres.get("presenter", {})
        print(f"  submissions/{p.get('role','phd')}s/{_folder_name(p)}/")


# ════════════════════════════════════════════════════════════════════════════════
# Sponsor logo resolution
# ════════════════════════════════════════════════════════════════════════════════

def _load_logo_file(path: str, h: int) -> Optional[Image.Image]:
    try:
        img   = Image.open(path).convert("RGBA")
        ratio = h / img.height
        return img.resize((max(1, int(img.width * ratio)), h), Image.LANCZOS)
    except Exception:
        return None


def _badge(name: str, h: int) -> Image.Image:
    w   = max(72, len(name) * 15)
    col = _BADGE_COLOURS.get(name.upper(), (55, 65, 105))
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w-1, h-1], radius=7, fill=(*col, 255))
    f   = _font("Poppins-Bold.ttf", h // 2)
    bb  = f.getbbox(name)
    tw, th = bb[2]-bb[0], bb[3]-bb[1]
    d.text(((w-tw)//2, (h-th)//2 - bb[1]//2), name, font=f, fill=(255,255,255,255))
    return img


def resolve_logo(entry, h: int, config_dir: Optional[Path] = None) -> Optional[Image.Image]:
    name, path = "", ""
    if isinstance(entry, dict):
        name, path = entry.get("name",""), entry.get("path","")
    elif isinstance(entry, str):
        if "/" in entry or "\\" in entry or "." in entry:
            path = entry;  name = Path(entry).stem
        else:
            name = entry

    if path and os.path.exists(path):
        img = _load_logo_file(path, h)
        if img: return img

    if name and config_dir:
        sd = config_dir / "assets" / "sponsors"
        if sd.exists():
            for f in sorted(sd.iterdir()):
                if f.stem.lower() == name.lower() and f.suffix.lower() in IMAGE_EXTS:
                    img = _load_logo_file(str(f), h)
                    if img: return img

    return _badge(name, h) if name else None


# ════════════════════════════════════════════════════════════════════════════════
# Drawing helpers
# ════════════════════════════════════════════════════════════════════════════════

def _draw_wrapped(draw, text: str, font, x: int, y: int,
                  max_w: int, fill: tuple, gap: int = 6) -> int:
    words = text.split()
    lines, cur = [], []
    for w in words:
        test = " ".join(cur + [w])
        if font.getbbox(test)[2] - font.getbbox(test)[0] <= max_w:
            cur.append(w)
        else:
            if cur: lines.append(" ".join(cur))
            cur = [w]
    if cur: lines.append(" ".join(cur))
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        bb  = font.getbbox(line)
        y  += bb[3] - bb[1] + gap
    return y


def _make_qr(url: str, size: int, bg: tuple = (0,0,0)) -> Image.Image:
    qr = qrcode.QRCode(version=1, box_size=10, border=3,
                       error_correction=qrcode.constants.ERROR_CORRECT_H)
    qr.add_data(url)
    qr.make(fit=True)
    return (qr.make_image(fill_color="white", back_color=bg)
              .convert("RGBA").resize((size, size), Image.LANCZOS))


def _load_photo(path: Optional[str], w: int, h: int) -> np.ndarray:
    if path and os.path.exists(path):
        try:
            img = cv2.imread(path)
            if img is not None:
                return cv2.resize(img, (w, h))
        except Exception:
            pass
    pil = Image.new("RGB", (w, h), (14, 14, 20))
    d   = ImageDraw.Draw(pil)
    cx, cy, hr = w//2, h//3, w//7
    d.ellipse([cx-hr, cy-hr, cx+hr, cy+hr],           fill=(68, 74, 92))
    br = w//4
    d.ellipse([cx-br, cy+hr+4, cx+br, cy+hr+4+br*2],  fill=(68, 74, 92))
    return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)


# ════════════════════════════════════════════════════════════════════════════════
# Video frame extraction
# ════════════════════════════════════════════════════════════════════════════════

def extract_frames(video_path: Optional[str], n: int, w: int, h: int) -> list[np.ndarray]:
    if video_path and os.path.exists(video_path):
        cap   = cv2.VideoCapture(video_path)
        total = max(1, int(cap.get(cv2.CAP_PROP_FRAME_COUNT)))
        idxs  = np.linspace(0, total - 1, n, dtype=int)
        frames: list[np.ndarray] = []
        for idx in idxs:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
            ret, frame = cap.read()
            frames.append(cv2.resize(frame, (w, h)) if ret
                          else np.zeros((h, w, 3), dtype=np.uint8))
        cap.release()
        return frames

    ph  = np.zeros((h, w, 3), dtype=np.uint8)
    pil = Image.fromarray(cv2.cvtColor(ph, cv2.COLOR_BGR2RGB))
    d   = ImageDraw.Draw(pil)
    f   = _font("Poppins-Light.ttf", 22)
    msg = "[ Project video not uploaded yet ]"
    bb  = f.getbbox(msg)
    d.text((w//2-(bb[2]-bb[0])//2, h//2-(bb[3]-bb[1])//2), msg, font=f, fill=(65, 70, 85))
    return [cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)] * n


# ════════════════════════════════════════════════════════════════════════════════
# Slide builders
# ════════════════════════════════════════════════════════════════════════════════

def build_intro_frame(conf: dict, theme: dict) -> np.ndarray:
    img  = _bg_pil(theme)
    draw = ImageDraw.Draw(img)
    acc  = theme["accent"]
    T    = theme["title"]
    Tx   = theme["text"]

    # Chrome
    draw.rectangle([0, 0, 7, HEIGHT], fill=acc)
    draw.rectangle([0, HEIGHT-4, WIDTH, HEIGHT], fill=acc)

    f_big   = _font("Poppins-Bold.ttf",    44)
    f_acr   = _font("Poppins-Medium.ttf",  26)
    f_date  = _font("Poppins-Regular.ttf", 20)
    f_label = _font("Poppins-Regular.ttf", 17)

    cx      = WIDTH // 2
    name    = conf.get("name", "Academic Conference")
    acronym = conf.get("acronym", "")
    date    = conf.get("date", "")

    if acronym:
        bb = f_acr.getbbox(acronym)
        draw.text((cx-(bb[2]-bb[0])//2, 130), acronym, font=f_acr, fill=acc)

    lines = textwrap.wrap(name, width=30)
    y = HEIGHT//2 - len(lines)*56//2 - 24
    for line in lines:
        bb = f_big.getbbox(line)
        draw.text((cx-(bb[2]-bb[0])//2, y), line, font=f_big, fill=T)
        y += 56

    if date:
        bb = f_date.getbbox(date)
        draw.text((cx-(bb[2]-bb[0])//2, y+10), date, font=f_date, fill=Tx)

    label = "Group Presentations"
    bb     = f_label.getbbox(label)
    tw, th = bb[2]-bb[0], bb[3]-bb[1]
    px, py = 16, 8
    rx0, ry0 = cx-tw//2-px, HEIGHT-95
    rx1, ry1 = cx+tw//2+px, ry0+th+py*2
    draw.rounded_rectangle([rx0, ry0, rx1, ry1], radius=5, fill=acc)
    draw.text((cx-tw//2, ry0+py), label, font=f_label, fill=theme["bg_pil"])

    return cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2BGR)


def build_outro_frame(group: dict, qr_url: str, theme: dict) -> np.ndarray:
    img  = _bg_pil(theme)
    draw = ImageDraw.Draw(img)
    acc  = theme["accent"]
    T    = theme["title"]
    Tx   = theme["text"]
    S    = theme["secondary"]

    draw.rectangle([0, 0, 7, HEIGHT], fill=acc)
    draw.rectangle([0, HEIGHT-4, WIDTH, HEIGHT], fill=acc)

    f_title   = _font("Poppins-Bold.ttf",    32)
    f_sub     = _font("Poppins-Medium.ttf",  19)
    f_regular = _font("Poppins-Regular.ttf", 16)
    f_light   = _font("Poppins-Light.ttf",   14)
    f_scan    = _font("Poppins-Regular.ttf", 14)
    f_ty      = _font("Poppins-Bold.ttf",    22)

    LEFT = 45;  SPLIT_X = int(WIDTH * 0.56);  y = 50

    for line in textwrap.wrap(group.get("name","Research Group"), width=26):
        bb = f_title.getbbox(line)
        draw.text((LEFT, y), line, font=f_title, fill=acc)
        y += bb[3]-bb[1]+8
    draw.rectangle([LEFT, y+10, LEFT+65, y+13], fill=T)
    y += 32

    pi = group.get("pi","")
    if pi:
        draw.text((LEFT, y), "Principal Investigator", font=f_light, fill=S)
        y += 18
        draw.text((LEFT, y), pi, font=f_sub, fill=T)
        y += 32

    members = group.get("members", [])
    if members:
        draw.text((LEFT, y), "Group Members", font=f_light, fill=S)
        y += 20
        half  = (len(members)+1)//2
        col_w = (SPLIT_X-LEFT)//2-8
        for j, m in enumerate(members):
            draw.text((LEFT+10+(j//half)*col_w, y+(j%half)*23),
                      f"• {m}", font=f_regular, fill=Tx)

    if group.get("website"):
        draw.text((LEFT, HEIGHT-84), group["website"], font=f_light, fill=(125,155,255))
    draw.text((LEFT, HEIGHT-58), "Thank you!", font=f_ty, fill=acc)

    if qr_url:
        qr_size = 195
        qr_x    = SPLIT_X + (WIDTH-SPLIT_X-qr_size)//2
        qr_y    = (HEIGHT-qr_size)//2 - 20
        img.paste(_make_qr(qr_url, qr_size, theme["bg_pil"]), (qr_x, qr_y))
        label = "Scan to visit us"
        bb    = f_scan.getbbox(label)
        pcx   = qr_x+qr_size//2
        draw.text((pcx-(bb[2]-bb[0])//2, qr_y+qr_size+10), label, font=f_scan, fill=acc)

    return cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2BGR)


def build_pres_overlay(pres: dict, index: int, total: int,
                       photo_bgr: np.ndarray,
                       config_dir: Path, theme: dict) -> np.ndarray:
    """Transparent RGBA overlay rendered once per slide (text, photo, logos)."""
    img  = Image.new("RGBA", (WIDTH, HEIGHT), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    acc  = theme["accent"]
    T    = theme["title"]
    Tx   = theme["text"]
    S    = theme["secondary"]

    f_title   = _font("Poppins-Bold.ttf",    28)
    f_authors = _font("Poppins-Regular.ttf", 17)
    f_pname   = _font("Poppins-Medium.ttf",  16)
    f_plabel  = _font("Poppins-Light.ttf",   13)
    f_counter = _font("Poppins-Light.ttf",   13)
    f_caption = _font("Poppins-Light.ttf",   16)
    f_funded  = _font("Poppins-Light.ttf",   13)

    # Counter
    counter = f"{index} / {total}"
    bb = f_counter.getbbox(counter)
    draw.text((WIDTH-(bb[2]-bb[0])-18, 6), counter, font=f_counter, fill=(*S, 150))

    # Title + gold rule + authors
    y = _draw_wrapped(draw, pres.get("title","Untitled"),
                      f_title, MARGIN, TITLE_Y, VIDEO_W-8, (*T, 255), gap=7)
    draw.rectangle([MARGIN, y+4, MARGIN+55, y+7], fill=(*acc, 200))
    y += 14
    _draw_wrapped(draw, pres.get("authors",""),
                  f_authors, MARGIN, y, VIDEO_W-8, (*S, 255), gap=4)

    # Presenter photo (right, vertically centred)
    ph_pil = Image.fromarray(cv2.cvtColor(photo_bgr, cv2.COLOR_BGR2RGB)).convert("RGBA")
    img.paste(ph_pil, (RIGHT_X, PHOTO_Y))
    bd = Image.new("RGBA", (RIGHT_W, PHOTO_H), (0,0,0,0))
    ImageDraw.Draw(bd).rectangle([0,0,RIGHT_W-1,PHOTO_H-1], outline=(*acc,180), width=2)
    img.paste(bd, (RIGHT_X, PHOTO_Y), bd)

    pname   = pres.get("presenter",{}).get("name","")
    label_y = PHOTO_Y + PHOTO_H + 8
    if pname:
        draw.text((RIGHT_X, label_y),    "Presenter:", font=f_plabel, fill=(*S,255))
        draw.text((RIGHT_X, label_y+17), pname,        font=f_pname,  fill=(*T,255))

    # Caption
    caption = pres.get("caption","")
    if caption:
        draw.text((MARGIN, CAPTION_Y), caption, font=f_caption, fill=(*Tx, 190))

    # Funding logos
    LOGO_H = 36
    logos  = pres.get("funding_logos", [])
    if logos:
        draw.text((MARGIN, LOGO_Y+11), "Supported by:", font=f_funded, fill=(*S,165))
        lx = MARGIN + 108
        for entry in logos:
            li = resolve_logo(entry, LOGO_H, config_dir)
            if li:
                img.paste(li, (lx, LOGO_Y+2), li)
                lx += li.width + 10

    return np.array(img)


# ════════════════════════════════════════════════════════════════════════════════
# Video assembly
# ════════════════════════════════════════════════════════════════════════════════

def _fade(out, a: np.ndarray, b: np.ndarray, n: int) -> None:
    af, bf = a.astype(np.float32), b.astype(np.float32)
    for i in range(n):
        alpha = i / n
        out.write(np.clip((1-alpha)*af + alpha*bf, 0, 255).astype(np.uint8))


def generate_video(config: dict, output_path: str, config_dir: Path) -> float:
    conf      = config.get("conference", {})
    pres_list = config.get("presentations", [])
    group     = config.get("group", {})
    qr_url    = config.get("qr_url", group.get("website",""))
    theme     = load_theme(config, config_dir)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out    = cv2.VideoWriter(output_path, fourcc, FPS, (WIDTH, HEIGHT))
    total_frames = 0

    # Intro
    intro_dur   = int(conf.get("duration", 5))
    intro_frame = build_intro_frame(conf, theme)
    n_main      = max(1, intro_dur*FPS - FADE_FRAMES)
    print(f"  Intro : {intro_dur}s")
    for _ in range(n_main): out.write(intro_frame)
    total_frames += n_main
    prev = intro_frame

    # Presentations
    for idx, pres in enumerate(pres_list):
        print(f"  [{idx+1}/{len(pres_list)}] {pres.get('title','')[:55]}")
        presenter  = pres.get("presenter",{})
        fl         = _folder_name(presenter)
        role       = presenter.get("role","phd")
        sub_dir    = _sub_folder(fl, role, config_dir)
        video_path = presenter.get("video") or _find_file(sub_dir, VIDEO_EXTS)
        photo_path = presenter.get("photo") or _find_file(sub_dir, PHOTO_EXTS)
        dur_s      = int(pres.get("duration", 5))
        n_frames   = dur_s * FPS

        vid_frames = extract_frames(video_path, n_frames, VIDEO_W, VIDEO_H)
        photo_bgr  = _load_photo(photo_path, RIGHT_W, PHOTO_H)
        overlay_np = build_pres_overlay(pres, idx+1, len(pres_list),
                                        photo_bgr, config_dir, theme)
        ov_a   = overlay_np[:,:,3:4].astype(np.float32)/255.0
        ov_bgr = overlay_np[:,:,:3][:,:,::-1].astype(np.float32)

        slide_frames = []
        for vf in vid_frames:
            canvas = theme["bg_frame"].copy()
            canvas[VIDEO_Y:VIDEO_Y+VIDEO_H, VIDEO_X:VIDEO_X+VIDEO_W] = vf
            composed = canvas.astype(np.float32)*(1-ov_a) + ov_bgr*ov_a
            slide_frames.append(np.clip(composed, 0, 255).astype(np.uint8))

        _fade(out, prev, slide_frames[0], FADE_FRAMES)
        total_frames += FADE_FRAMES
        for frame in slide_frames: out.write(frame)
        total_frames += len(slide_frames)
        prev = slide_frames[-1]

    # Outro
    outro_dur   = int(group.get("duration", 8))
    outro_frame = build_outro_frame(group, qr_url, theme)
    print(f"  Outro : {outro_dur}s")
    _fade(out, prev, outro_frame, FADE_FRAMES)
    total_frames += FADE_FRAMES
    for _ in range(outro_dur*FPS): out.write(outro_frame)
    total_frames += outro_dur*FPS

    out.release()
    duration_s = total_frames / FPS
    print(f"  ✓ Silent video → {output_path}  ({duration_s:.1f} s)")
    return duration_s


# ════════════════════════════════════════════════════════════════════════════════
# Entry point
# ════════════════════════════════════════════════════════════════════════════════

def main():
    script_dir  = Path(__file__).parent
    config_path = Path(sys.argv[1]) if len(sys.argv) > 1 else script_dir/"config.json"
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else script_dir/"output_video.mp4"

    if not config_path.exists():
        sys.exit(f"ERROR: config not found: {config_path}")

    with open(config_path) as fh:
        config = json.load(fh)
    config_dir = config_path.parent

    print("─── Creating folders ───────────────────────────────")
    create_asset_folders(config, config_dir)

    # Music path
    music_cfg  = config.get("music", {})
    custom_path = music_cfg.get("path","").strip()
    if custom_path and os.path.exists(config_dir/custom_path):
        music_path = str(config_dir/custom_path)
    else:
        music_path = str(config_dir/"assets"/"music"/"background.wav")

    print("\n─── Rendering video ────────────────────────────────")
    silent = str(output_path).replace(".mp4","_silent.mp4")
    duration_s = generate_video(config, silent, config_dir)

    # (Re)generate music if using the auto path
    if music_path == str(config_dir/"assets"/"music"/"background.wav"):
        style = music_cfg.get("style", "house")
        generate_music(style, duration_s + 2, music_path)

    print("\n─── Mixing audio ───────────────────────────────────")
    volume = float(music_cfg.get("volume", 0.22))
    if mix_audio(silent, music_path, str(output_path), duration_s, volume):
        try: os.remove(silent)
        except OSError: pass
        print(f"  ✓ Final video → {output_path}")
    else:
        import shutil
        try:
            shutil.move(silent, str(output_path))
        except Exception:
            pass
        print("  (audio mixing skipped — silent video saved)")

    print(f"\nDone ✓  →  {output_path}")


if __name__ == "__main__":
    main()

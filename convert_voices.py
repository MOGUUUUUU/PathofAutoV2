#!/usr/bin/env python3
"""Regenerate PoE item filter sounds with a custom voice clone."""

import os
import sys
import json
import base64
import struct
import io
import time
import wave
import audioop
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import requests

API_ENDPOINT = "https://api.xiaomimimo.com/v1/chat/completions"
MODEL = "mimo-v2-tts"

# Read API key from env or config
API_KEY = os.environ.get("MIMO_API_KEY", "")
API_KEY = "sk-ci5dfkl2469y2nf5rjwoc4joeowwy2dl4eamtvq0v9l0ntae"
# if not API_KEY:
#     cfg_path = os.path.expanduser("~/.openclaw/openclaw.json")
#     try:
#         with open(cfg_path) as f:
#             cfg = json.load(f)
#         API_KEY = cfg["models"]["providers"]["xiaomi"]["apiKey"]
#     except Exception:
#         print("Error: No API key found", file=sys.stderr)
#         sys.exit(1)

# Load voice sample
VOICE_SAMPLE_PATH = sys.argv[1] if len(sys.argv) > 1 else "a_f7.wav"
INPUT_DIR = sys.argv[2] if len(sys.argv) > 2 else "音效"
OUTPUT_DIR = sys.argv[3] if len(sys.argv) > 3 else "音色重构"

with open(VOICE_SAMPLE_PATH, "rb") as f:
    voice_b64 = base64.b64encode(f.read()).decode()

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Get list of files
files = sorted([f for f in os.listdir(INPUT_DIR) if f.endswith(".mp3")])
total = len(files)
print(f"Found {total} files to process")

def gen_tts(text, out_wav):
    """Generate TTS with voice clone, save as WAV."""
    payload = {
        "model": MODEL,
        "audio": {
            "format": "wav",
            "voice_audio": {"format": "wav", "data": voice_b64}
        },
        "messages": [{
            "role": "assistant",
            "content": f"<style>元气满满 欢快活泼</style>{text}"
        }]
    }
    
    resp = requests.post(
        API_ENDPOINT,
        headers={"Content-Type": "application/json", "api-key": API_KEY},
        json=payload,
        timeout=300
    )
    
    if resp.status_code != 200:
        print(f"  API error {resp.status_code}: {resp.text[:200]}", file=sys.stderr)
        return False
    
    data = resp.json()
    if "error" in data:
        print(f"  API error: {data['error']}", file=sys.stderr)
        return False
    
    try:
        audio_data = data["choices"][0]["message"]["audio"]["data"]
        raw = base64.b64decode(audio_data)
    except (KeyError, IndexError, TypeError) as e:
        print(f"  Response error: {e}", file=sys.stderr)
        return False
    
    # Write WAV (handle both raw PCM and existing WAV)
    with open(out_wav, "wb") as f:
        if raw[:4] == b"RIFF":
            f.write(raw)
        else:
            # Wrap raw PCM: 24kHz, 16-bit, mono
            sr, bps, ch = 24000, 16, 1
            br = sr * ch * bps // 8
            buf = io.BytesIO()
            buf.write(b"RIFF")
            buf.write(struct.pack("<I", 36 + len(raw)))
            buf.write(b"WAVEfmt ")
            buf.write(struct.pack("<IHHIIHH", 16, 1, ch, sr, br, ch * bps // 8, bps))
            buf.write(b"data")
            buf.write(struct.pack("<I", len(raw)))
            buf.write(raw)
            f.write(buf.getvalue())
    
    return True

def wav_to_mp3(wav_path, mp3_path):
    """Convert WAV to MP3 using pure Python (lameenc)."""
    import lameenc

    with wave.open(wav_path, "rb") as wf:
        sr = wf.getframerate()
        ch = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        pcm = wf.readframes(wf.getnframes())

    # lameenc requires 16-bit PCM
    if sampwidth != 2:
        pcm = audioop.lin2lin(pcm, sampwidth, 2)

    encoder = lameenc.Encoder()
    encoder.set_bit_rate(192)
    encoder.set_in_sample_rate(sr)
    encoder.set_channels(ch)
    encoder.set_quality(2)

    mp3_data = encoder.encode(pcm)
    mp3_data += encoder.flush()

    with open(mp3_path, "wb") as f:
        f.write(mp3_data)

MAX_WORKERS = 10
print_lock = threading.Lock()
counter_lock = threading.Lock()
done_count = 0

def process_one(i, fname):
    global done_count
    item_name = fname.replace(".mp3", "")
    out_wav = os.path.join(OUTPUT_DIR, fname.replace(".mp3", ".wav"))
    out_mp3 = os.path.join(OUTPUT_DIR, fname)

    if os.path.exists(out_mp3):
        with print_lock:
            print(f"[{i}/{total}] SKIP {fname} (already exists)")
        return

    try:
        t0 = time.time()
        if gen_tts(item_name, out_wav):
            wav_to_mp3(out_wav, out_mp3)
            os.remove(out_wav)
            elapsed = time.time() - t0
            size = os.path.getsize(out_mp3)
            with print_lock:
                print(f"[{i}/{total}] {item_name} OK ({size/1024:.0f}KB, {elapsed:.1f}s)")
        else:
            with print_lock:
                print(f"[{i}/{total}] {item_name} FAILED")
    except Exception as e:
        with print_lock:
            print(f"[{i}/{total}] {item_name} ERROR: {e}")

    with counter_lock:
        done_count += 1

print(f"Starting with {MAX_WORKERS} workers...")

with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
    futures = {pool.submit(process_one, i, fname): fname for i, fname in enumerate(files, 1)}
    for future in as_completed(futures):
        future.result()  # raise if unexpected error

print(f"\nDone! Output in {OUTPUT_DIR}/")

#!/usr/bin/env python3
"""Bridge between Hermes and Voicebox.

Hermes runs this as a "command" voice provider. It hands us a text file and
an output path; we ask the local Voicebox app to speak the text, then save
the audio where Hermes expects it.

Usage (Hermes fills in the paths):
    python3 voicebox_tts.py INPUT_TEXT_FILE OUTPUT_AUDIO_FILE [--voice PROFILE_ID]

Run with --list-voices to see the voice profiles Voicebox has.

Only the Python standard library is used. ffmpeg is needed only when the
output file is not .wav.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

DEFAULT_URL = "http://127.0.0.1:17493"
DEFAULT_LANGUAGE = "en"
ENGINES = ("qwen", "qwen_custom_voice", "luxtts", "chatterbox",
           "chatterbox_turbo", "tada", "kokoro")


class BridgeError(Exception):
    """A problem we can explain to Dan in plain words."""


def log(message):
    # Hermes resets its idle timer whenever we print, and shows stderr if we fail.
    print(f"[voicebox] {message}", file=sys.stderr, flush=True)


def request(url, method="GET", body=None, timeout=300):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as err:
        detail = err.read().decode("utf-8", "replace")[:500]
        raise BridgeError(f"Voicebox said no ({err.code}) to {method} {url}: {detail}")
    except urllib.error.URLError as err:
        raise BridgeError(
            f"Can't reach Voicebox at {url} ({err.reason}). "
            "Is the Voicebox app open?")


def list_profiles(base_url):
    raw = json.loads(request(f"{base_url}/profiles", timeout=30))
    if isinstance(raw, dict):
        raw = raw.get("profiles") or raw.get("items") or []
    return raw


def describe_profiles(profiles):
    if not profiles:
        return "  (none yet: create a voice in the Voicebox app first)"
    lines = []
    for p in profiles:
        extras = ", ".join(f"{k}: {p[k]}" for k in ("language", "engine", "default_engine")
                           if p.get(k))
        lines.append(f"  {p.get('id')}  {p.get('name', '')}" + (f"  ({extras})" if extras else ""))
    return "\n".join(lines)


def generate(base_url, text, profile_id, engine, language):
    body = {"text": text, "profile_id": profile_id, "language": language}
    if engine:
        body["engine"] = engine  # otherwise Voicebox uses its own default
    log(f"Generating speech ({len(text)} characters, engine {engine or 'default'})")
    meta = json.loads(request(f"{base_url}/generate", "POST", body))
    generation_id = meta.get("id")
    if not generation_id:
        raise BridgeError(f"Voicebox didn't return a generation id: {meta}")
    log(f"Downloading audio for generation {generation_id}")
    return request(f"{base_url}/audio/{generation_id}")


def save_audio(wav_bytes, output_path):
    output_path = os.path.expanduser(output_path)
    out_dir = os.path.dirname(os.path.abspath(output_path))
    if output_path.lower().endswith(".wav"):
        with open(output_path, "wb") as f:
            f.write(wav_bytes)
        return

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise BridgeError(
            "ffmpeg is needed to make this audio format. "
            "Install it with: brew install ffmpeg")
    with tempfile.NamedTemporaryFile(suffix=".wav", dir=out_dir, delete=False) as tmp:
        tmp.write(wav_bytes)
        tmp_path = tmp.name
    try:
        cmd = [ffmpeg, "-y", "-loglevel", "error", "-i", tmp_path]
        if output_path.lower().endswith((".ogg", ".opus")):
            cmd += ["-c:a", "libopus", "-b:a", "32k"]
        cmd.append(output_path)
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise BridgeError(f"ffmpeg couldn't convert the audio: {result.stderr.strip()}")
    finally:
        os.remove(tmp_path)


def parse_args(argv):
    p = argparse.ArgumentParser(description="Speak Hermes replies with Voicebox.")
    p.add_argument("input_path", nargs="?", help="Text file Hermes wrote")
    p.add_argument("output_path", nargs="?", help="Where to save the audio")
    p.add_argument("--voice", default=os.environ.get("VOICEBOX_PROFILE_ID", ""),
                   help="Voicebox voice profile id")
    p.add_argument("--engine", default=os.environ.get("VOICEBOX_ENGINE", ""),
                   choices=("",) + ENGINES,
                   help="Speech engine; leave out to use Voicebox's default")
    p.add_argument("--language", default=os.environ.get("VOICEBOX_LANGUAGE", DEFAULT_LANGUAGE))
    p.add_argument("--url", default=os.environ.get("VOICEBOX_URL", DEFAULT_URL))
    p.add_argument("--list-voices", action="store_true",
                   help="Show the voice profiles in Voicebox and exit")
    args = p.parse_args(argv)
    if not args.list_voices and not (args.input_path and args.output_path):
        p.error("INPUT and OUTPUT paths are required (or use --list-voices)")
    return args


def main(argv=None):
    args = parse_args(argv)
    base_url = args.url.rstrip("/")
    try:
        if args.list_voices:
            print(describe_profiles(list_profiles(base_url)))
            return 0

        with open(os.path.expanduser(args.input_path), encoding="utf-8") as f:
            text = f.read().strip()
        if not text:
            raise BridgeError("There's no text to speak.")

        if not args.voice:
            raise BridgeError(
                "No voice chosen. Set `voice:` in the Hermes tts settings to one of these ids:\n"
                + describe_profiles(list_profiles(base_url)))

        wav = generate(base_url, text, args.voice, args.engine, args.language)
        save_audio(wav, args.output_path)
        log(f"Saved {args.output_path}")
        return 0
    except (BridgeError, OSError) as err:
        log(f"Error: {err}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

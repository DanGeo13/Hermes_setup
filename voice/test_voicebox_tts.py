"""Tests for the Voicebox bridge, using a fake Voicebox server.

Run with: python3 -m unittest voice/test_voicebox_tts.py
"""

import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.dirname(__file__))
import voicebox_tts  # noqa: E402

FAKE_WAV = b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00@\x1f\x00\x00\x80>\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00"


class FakeVoicebox(BaseHTTPRequestHandler):
    requests = []

    def log_message(self, *args):
        pass

    def _send(self, code, body, content_type="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        FakeVoicebox.requests.append(("GET", self.path, None))
        if self.path == "/profiles":
            self._send(200, json.dumps([{"id": "abc123", "name": "Voice Bot"}]).encode())
        elif self.path == "/audio/gen-1":
            self._send(200, FAKE_WAV, "audio/wav")
        else:
            self._send(404, b'{"detail":"not found"}')

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeVoicebox.requests.append(("POST", self.path, body))
        if body.get("profile_id") != "abc123":
            self._send(404, b'{"detail":"Profile not found"}')
        else:
            self._send(200, json.dumps({"id": "gen-1", "audio_path": "/x.wav"}).encode())


class BridgeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), FakeVoicebox)
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        FakeVoicebox.requests = []
        self.dir = tempfile.mkdtemp()
        self.text = os.path.join(self.dir, "in.txt")
        with open(self.text, "w", encoding="utf-8") as f:
            f.write("G'day Dan, this is Hermes.")

    def tearDown(self):
        shutil.rmtree(self.dir)

    def run_bridge(self, *extra, out="out.wav"):
        out_path = os.path.join(self.dir, out)
        code = voicebox_tts.main([self.text, out_path, "--url", self.url, *extra])
        return code, out_path

    def test_saves_wav_from_voicebox(self):
        code, out = self.run_bridge("--voice", "abc123")
        self.assertEqual(code, 0)
        with open(out, "rb") as f:
            self.assertEqual(f.read(), FAKE_WAV)
        method, path, body = FakeVoicebox.requests[0]
        self.assertEqual((method, path), ("POST", "/generate"))
        self.assertEqual(body["text"], "G'day Dan, this is Hermes.")
        self.assertNotIn("engine", body)

    def test_passes_engine_when_given(self):
        code, _ = self.run_bridge("--voice", "abc123", "--engine", "qwen")
        self.assertEqual(code, 0)
        self.assertEqual(FakeVoicebox.requests[0][2]["engine"], "qwen")

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg not installed")
    def test_converts_to_ogg_with_ffmpeg(self):
        code, out = self.run_bridge("--voice", "abc123", out="out.ogg")
        self.assertEqual(code, 0)
        with open(out, "rb") as f:
            self.assertEqual(f.read(4), b"OggS")

    def test_missing_voice_lists_profiles(self):
        code, out = self.run_bridge()
        self.assertEqual(code, 1)
        self.assertFalse(os.path.exists(out))

    def test_unknown_voice_fails(self):
        code, out = self.run_bridge("--voice", "nope")
        self.assertEqual(code, 1)
        self.assertFalse(os.path.exists(out))

    def test_voicebox_not_running(self):
        out = os.path.join(self.dir, "out.wav")
        code = voicebox_tts.main([self.text, out, "--voice", "abc123",
                                  "--url", "http://127.0.0.1:1"])
        self.assertEqual(code, 1)
        self.assertFalse(os.path.exists(out))


if __name__ == "__main__":
    unittest.main()

# Hermes voice with Voicebox

Hermes can answer you in Telegram with a voice bubble in your own Voicebox
voice. `voicebox_tts.py` is the small bridge: Hermes hands it the reply text,
it asks the Voicebox app on your Mac to speak it, and saves the audio for
Hermes to send.

## What you need

- Hermes already chatting with you in Telegram by text.
- The Voicebox app open on the same Mac, with a voice you've made.
- ffmpeg: `brew install ffmpeg opus`
- This repository on your Mac: `git clone https://github.com/DanGeo13/hermes_setup ~/Hermes_setup`

## Set it up

1. **Find your voice id.** With Voicebox open, run this in Terminal:

   ```bash
   python3 ~/Hermes_setup/voice/voicebox_tts.py --list-voices
   ```

   You'll see each voice's id and name. Copy the id of the one you want.

2. **Try one line by itself.** Replace `YOUR-ID` and run:

   ```bash
   echo "G'day, this is Hermes." > /tmp/hermes-test.txt
   python3 ~/Hermes_setup/voice/voicebox_tts.py /tmp/hermes-test.txt /tmp/hermes-test.wav --voice YOUR-ID
   open /tmp/hermes-test.wav
   ```

   You should hear your voice. If not, the message it prints says why.

3. **Tell Hermes to use it.** Copy the settings from
   [`hermes-tts.example.yaml`](hermes-tts.example.yaml) into
   `~/.hermes/config.yaml`, and paste your voice id into `voice:`.

4. **Restart Hermes** with `hermes gateway`.

5. **Turn voice on in Telegram.** Send `/voice on` to your bot. Hermes now
   speaks when you send it a voice note. (`/voice tts` makes it speak every
   reply, `/voice off` turns it off.)

## Options

| Option | What it does |
| --- | --- |
| `--voice ID` | Which Voicebox voice to use (required) |
| `--engine NAME` | Force a speech engine, e.g. `kokoro` or `qwen`. Leave it out to use Voicebox's default. |
| `--language CODE` | Language of the text, default `en` |
| `--url URL` | Where Voicebox is listening, default `http://127.0.0.1:17493` |

## If something goes wrong

- **"Can't reach Voicebox… Is the Voicebox app open?"**: open Voicebox and try again.
- **"Voicebox said no (404)… Profile not found"**: the voice id is wrong. Run `--list-voices` again.
- **The reply is a file, not a voice bubble**: install ffmpeg (`brew install ffmpeg opus`) and restart Hermes.

## Run the tests

```bash
python3 -m unittest voice/test_voicebox_tts.py
```

The tests use a pretend Voicebox, so they don't need the app running.

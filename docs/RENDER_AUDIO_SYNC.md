# Render audio lifecycle correction

The 2.5-second SPIN clip previously ended while the LED wheel was still waiting
for the server or decelerating. The wheel now owns a sustained audio source:
it loops the published trim and stops at center lock, cancellation, or hiding
the page. Request tokens prevent a late decode/resume from starting stale audio.

Splash and gameplay BGM are decoded before PLAY and use the shared Web Audio
mixer when available. BGM starts on gameplay entry; the native media fallback
remains available for interrupted contexts and clears its reservation mute.
Effects no longer drive music through the effects compressor. The published
master/music/SFX settings and all uploaded files remain unchanged.

Splash fades honor their full saved duration, and the cover transition follows
the audio clock. The completion hold and fade fit inside the selected intro.
The existing content-derived UI release and revalidation headers refresh clients.

## Validation

Run `node tests/qa_audio_sync.cjs` with Python requirements and Node Playwright
installed, plus a Playwright Chromium browser. `UNO_QA_CHROMIUM` may select a
locally installed test executable. The harness starts a disposable localhost
server and uses a separate SQLite file under `fixtures/`. It refuses live URLs.

The fixture manifest preserves the reported trims/mixer. If read-only copies of
the published MP3s are present at `fixtures/<cue>.mp3`, it tests those files;
otherwise it generates deterministic PCM cues with matching durations.

Assertions cover splash/gameplay timing within 100ms, one BGM source with
nonzero audio samples before any gameplay tap, normal/turbo/delayed-server
SPIN stopping within 50ms of center lock, cancelled async starts, and the
interrupted-context native-media fallback. Real speaker/headphone output and
physical iPhone Safari still require device acceptance testing.

Deploy this commit specifically to the Render staging service. Do not merge
into or redeploy the Railway source branch while its old database backup is
blocked. This change contains no database migrations or sound-profile writes.

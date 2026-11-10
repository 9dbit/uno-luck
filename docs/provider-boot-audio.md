# Provider boot and public audio

The provider entrypoint exposes the existing public `GET /api/sounds/manifest`
and `GET /api/sounds/files/{cue}` handlers. It does not mount Sound Studio's
admin check, health write probe, mixer mutation, cue publishing/settings or
deletion routes. Ordinary playback needs no admin credential. The existing cue
whitelist, filename checks, MIME types and `nosniff` remain in effect.

The shared sound storage helper may initialize the configured catalog/audio
directories during a read. These routes do not publish catalog entries or access
the native wallet database. Unconfigured storage still honestly reports
`ready: false` with an empty catalog; corrupt or unavailable configured storage
still returns its existing 503 response. A published file that is missing still
returns 503. No server error is converted into successful audio bytes.

## Optional splash catalog

The Sound Studio client prepares the existing tracked
`/assets/audio/music-loop.mp3` when there is no available custom splash cue:
for example an empty catalog, an unavailable catalog without a cached custom
cue, or a local custom draft that has lost its audio bytes.
Preparing a URL does not report playback success. The unchanged boot controller
still requires the visible **Play with Sound** click, synchronous browser
`HTMLMediaElement.play()` calls and successful playback promises before entering
the game. No autoplay policy override or silent bypass is introduced.

A custom published file may exist in the catalog but fail to play. That attempt
still fails visibly. The client prepares the bundled track for the next Play
click; it never starts a replacement asynchronously after a rejected gesture.
If the bundled audio also fails, boot remains blocked with the existing retry
control. The fallback uses its own 0–7 second bounds on the tracked 14.616 second
clip, so a long custom clip's trim cannot seek beyond the fallback. Saved local
and published sound settings remain unchanged. Existing published custom clips
retain their trim/fade behavior, and the separate music lane continues to honor
the user's music preference and the original gesture/boot handoff.

The locked game shell, boot controller, game client, RNG/math, wallet operations,
locks, worker instrumentation and default 40-token limiter are unchanged.

## Native history metadata

The native round presentation wrapper includes the existing persisted Unix
`created_at` value. The locked History Bet client requires that timestamp to
format its history date; without it, a completed native round rendered
`Invalid time value`. The locked outcome presenter is unchanged and the timestamp
is the only added response field. No outcomes, cards, money, storage schema,
callbacks or transaction boundaries change. A state/history regression checks
the active and settled round representations against the locked presenter and
verifies the database is unchanged by the read.

## Validation

`tests/test_provider_sound_readonly.py` exercises the actual provider HTTP
routes: public metadata/file responses, exact tracked asset bytes, honest empty
and unavailable catalogs, unsafe storage names, and absent mutation/admin routes
even when a valid-looking admin header is supplied. The existing provider
qualification workflow retains all prior gates and adds these tests and the
existing splash/audio regressions.

`tests/visual_qa_provider_boot_audio.py` runs actual Chromium media playback with
the checked-in audio/splash scripts in a loopback component fixture. It covers
empty and unconfigured catalogs, a catalog outage, a published clip, a broken
custom file requiring a new click, a missing local draft, music disabled, and
failure of the bundled audio itself. It observes the real `play()` result and
trusted click, checks no pre-click playback or automatic replacement playback,
and preserves media state/screenshots. It does not simulate a successful media
play, initiate game rounds or mutate wallet state.
Unavailable media durations are recorded as `null`; report serialization rejects
nonfinite numbers so the evidence remains strict JSON.

```bash
python -m pytest -q tests/test_provider_sound_readonly.py \
  tests/test_v11_splash_sound_reload.py tests/test_v11_sound_lifecycle.py \
  tests/test_v11_ios_safari_audio.py
python tests/visual_qa_provider_boot_audio.py
```

The browser script accepts `UNO_BOOT_AUDIO_OUT` for a separate evidence directory
and `UNO_BOOT_CHROMIUM_EXECUTABLE` for an already installed Chromium executable.
CI installs Playwright 1.51.1 with its matching Chromium. A local run must record
the actual runtime; an executable override does not alter browser audio policy.

This component result is separate from Genesis's unchanged native UI
conformance. That suite must use an exact committed UNO candidate, actual
isolated native engines and the real Genesis/Soft Tech fixture before claiming
native launch, Spin, history and wallet acceptance. Chromium media acceptance
does not establish physical speaker output or Safari/iPhone acceptance.

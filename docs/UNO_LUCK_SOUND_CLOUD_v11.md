# UNO LUCK v1.1 · Sound Cloud (staging)

## Purpose

The 12 custom sound cues, their START/STOP/DURATION, FADE IN/OUT,
background-music REPEAT, and Master/Music/SFX levels are now published to
one server catalog. The app on desktop and iPhone reads the same manifest
and versioned audio bytes. The audio catalog does not touch the gameplay
ledger, RNG, coin balances or payouts.

## First migration of desktop sound files

Audio uploaded before Sound Cloud was created remains in that **desktop
browser's IndexedDB**, not on Railway. There is no remote access to those
files until their owner chooses to publish them.

1. Open the **same desktop browser and origin** where the 12 files were uploaded.
2. Open **Menu → Sound Studio → PUBLISH SOUND DARI DESKTOP · ADMIN**.
3. In Railway, open project UNO LUCK → service `uno-luck-web` →
   **staging** → Variables; reveal/copy `UNO_SOUND_ADMIN_TOKEN`.
   Never paste the value in chat or the GitHub repository.
4. Enter it in Sound Studio and press **VERIFIKASI KUNCI**.
5. Press **☁ PUBLISH ALL 12 SOUND LIST**. Wait for the success
   confirmation. Only locally changed/imported cues are uploaded;
   built-in defaults remain built-in.
6. On iPhone, open the **same staging URL** in Safari or WebView,
   let the audio cloud synchronize, then tap **START WITH SOUND**.
   iOS still requires a tap to enable audible playback.

After enabling the admin key in that desktop tab, future file UPLOAD,
SAVE trim/fade, RESET and mixer changes publish automatically.
Ordinary game users do not need an admin key: playback is read-only.

## Operational notes

- Railway staging volume: `uno-luck-shared-sounds-staging`,
  mounted at `/data/uno-luck-audio` and selected by
  `UNO_SOUND_STORAGE_DIR`. Do not delete or reset the volume.
- `UNO_SOUND_ADMIN_TOKEN` is a high-entropy secret in Railway staging
  Variables, never in client code or documentation.
- Max custom file 16 MiB. Source data is atomically committed.
- Sound manifest: `GET /api/sounds/manifest` (no-store).
- Published audio: `GET /api/sounds/files/{cue}?v={revision}`.
- Clients recheck on page load/return to tab and approximately every 45s.
- Empty/unpublished cues fall back to original built-in audio.
- Existing local audio drafts are never deleted by migration.
- Real iPhone speaker verification is a separate device QA gate;
  a simulated iPhone browser cannot certify physical output.

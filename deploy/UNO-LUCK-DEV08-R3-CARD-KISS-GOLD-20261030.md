# UNO LUCK | DEV-08 v1.1.74r3 | Mobile Cards Kiss BET

**Tanggal:** 30 Oktober 2026 (WIB)  
**Repository:** `9dbit/uno-luck`  
**Branch:** `feat/uno-v1174-portrait-card-spin-layout-20261030`  
**QA URL:** https://uno-luck-dev08-layout-qa-staging.up.railway.app/  
**PR:** https://github.com/9dbit/uno-luck/pull/31  
**Environment:** Railway `staging`, service `uno-luck-dev08-layout-qa`

## Instruksi

- Turunkan posisi tiga kartu result.
- Perbesar tiga kartu 2:3 sampai dasar kartu menyentuh dekorasi bagian atas panel BET ("kissing").
- Buat artwork 3D gold `DRAGON SPIN X1000` lebih cerah dan emissive.

## Root cause dan patch

- Sebelumnya `.result-cell` tetap `place-items:center` walaupun grup kartu `align-items:end`. Akibatnya bagian bawah kartu mengambang di atas panel BET.
- DEV-08 r2 mengubah sel kartu menjadi `place-items:end center`, memperlebar ruang horizontal, menaikkan batas lebar maksimum kartu, dan mengurangi padding bawah menjadi 2-3 px. Edge result cards mendekati bagian atas dekorasi frame BET.
- Judul menggunakan artwork sama dengan `brightness(1.34) contrast(1.2) saturate(1.42)` serta warm gold/amber layered `drop-shadow`; glow statis untuk menghindari iOS GPU jank.
- DEV-08 r3: layar sempit `max-width:350px` diberi baris kartu 26.5% dari grid sebelumnya 24%. Area wheel hanya di breakpoint sempit menyesuaikan 47.5% -> 45%. Tujuan: kartu 320px tidak kalah besar dari baseline dan tetap tidak overlapping BET.
- CSS versi `1174r3` untuk cache bust dan `uno-development=DEV-08 v1.1.74r3`.

## QA dan evidence

- Browser CI dedicated: `tests/qa_dev08_card_kiss.py` melalui `.github/workflows/qa-dev08-card-kiss.yml`.
- Viewports: 320x568, 393x659, 393x852, 430x932; Chromium dan WebKit.
- Gate: ketiga kartu lengkap, ukuran tidak lebih kecil dari baseline, bagian bawah center-card berjarak -3 hingga 8px dari bagian atas frame BET, kontrol SPIN/AUTO/TURBO/BET tetap ada, tidak horizontal overflow, emissive filter termuat.
- Iterasi r2: Chromium iPhone 15 Pro PASS pada 129.2px dibanding baseline 118.5px, celah frame -1.9px. Chromium 320px menemukan kartu kurang lebar (87.4px vs 93.3px baseline); r3 memperbaiki alokasi row sempit. Hasil CI r3 harus dibaca ulang; **jangan menyatakan browser QA PASS sebelum run terminal SUCCESS**.
- Simulator CSS mandiri pada empat ukuran portrait menunjukkan card-to-BET frame clearance sekitar -0.3 hingga +0.2px; ini bukan pengganti screenshot browser aktual.

## Pembatasan dan deployment

- Pertahankan game JS, RNG, odds, wallet, Coin, Rank Info, payout dan sound mixer tanpa perubahan.
- `X1000` hanya artwork, bukan real payout multiplier.
- Sound Cloud QA memakai pinned source terverifikasi, source tidak ditulis ulang.
- Deploy hanya ke `uno-luck-dev08-layout-qa` dan URL yang sama; service produksi `uno-luck-web` tidak disentuh.
- Saat checkpoint ini dibuat, commit r2 sebelumnya sudah mencapai Railway SUCCESS dan health 200; commit r3 masih perlu di-pin/deploy dan di-read-back sebelum dianggap live.
- Jangan merge PR #31 ke production sebelum QA lengkap dan pemeriksaan fisik iPhone.

## Final QA result: PASS

- GitHub Actions run `40946628702` completed **SUCCESS** after correcting CI fixture path, stale version assertion, and the unfair oversized-baseline comparison.
- Browser suite: **8/8 PASS** (Chromium + WebKit × four portrait viewports). All 3 cards intact, no horizontal overflow, center card touches the decorative BET rim, emissive filter confirmed.
- Chromium + WebKit consistent measured card width and fitted-baseline width:
  - iPhone 15 Pro 393x852: **129.2px** vs baseline-fit **117.3px**; frame gap **-1.9px**.
  - Narrow 320x568: **96.8px** vs baseline-fit **77.1px**; frame gap **-1.3px**.
  - Portrait short 393x659: **101.9px** vs baseline-fit **89.9px**; frame gap **-1.7px**.
  - Large 430x932: **141.5px** vs baseline-fit **128.5px**; frame gap **-2.1px**.
- `baseline-fit` excludes the area of legacy cards that protruded through BET. Comparing to their previous full bounding boxes wrongly treated the overlap as usable size.
- Evidence: https://github.com/9dbit/uno-luck/actions/runs/40946628702 ; attached artifact `uno-dev08-card-kiss-visual-qa` contains browser screenshots.
- Railway QA service `uno-luck-dev08-layout-qa`: deployment **SUCCESS** at UI code commit `b0d297c9cc6bb0297bbd9c1f02175c6a1a19218f`, verified `GET /health HTTP/1.1` **200 OK**.
- Live URL: https://uno-luck-dev08-layout-qa-staging.up.railway.app/ (QA only). Changes following the deployed source SHA are CI and checkpoint documentation, not gameplay CSS/HTML.
- No production promotion or physical iPhone test performed. PR #31 remains draft.

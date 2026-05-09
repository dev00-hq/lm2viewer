# M5 Inspector Routing Validation - 2026-05-07

## Setup

- URL: `http://127.0.0.1:8894`
- Server command: `C:\Python312\python.exe -m lba2_lm2_viewer.viewer --host 127.0.0.1 --port 8894 --asset-root D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2 --no-browser`
- Asset root: `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`
- Screenshot: `docs/validation-m5-inspector-routing-2026-05-07.png`

## Selection

- Selected id: `SAMPLES.HQR:0`
- Selection path: Explorer search for `SAMPLES.HQR:0`, then the sample resource row.

## Expected State

- Active selection remains an `ASSET` selection for `SAMPLES.HQR:0`.
- Workspace suggestion is `resource`.
- Export button is enabled from graph-backed export capability.
- Inspector route is the graph-projected `sample_audio` route and shows sample
  audio sections.
- Resource workspace title matches the selected sample.

## Observed State

- Active selection showed `Sample 0 pcm 1ch 8-bit 22050Hz (SAMPLES.HQR:0)`.
- Kind showed `ASSET`.
- Stable ID showed `SAMPLES.HQR:0`.
- Workspace showed `resource`.
- `#exportAsset.disabled` was `false`.
- Inspector reported `7 structured inspector sections` and included `Audio`
  with sample format, channels, sample rate, sample frames, duration, and data
  bytes.
- `#resourceTitle` showed `Sample 0 pcm 1ch 8-bit 22050Hz (SAMPLES.HQR:0)`.

Result: passed.

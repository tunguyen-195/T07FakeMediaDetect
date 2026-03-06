# Demo Runbook

## Scope

- Live demo target: `image + pdf`
- Runtime: active release `run_20260306_055001`
- Demo assets: `sample_sets/demo_pack`

## Pre-demo Checklist

1. `git pull`
2. `cd webapp`
3. `install.bat`
4. `status.bat`
5. `start.bat`
6. `python scripts/preflight_demo_assets.py`

## What To Demo

1. Upload 2 authentic JPEGs from `sample_sets/demo_pack/selected_good_cases/authentic/`
2. Upload 2 forged JPEGs from `sample_sets/demo_pack/selected_good_cases/forged/`
3. Upload `sample_sets/demo_pack/pdf/demo_authentic_pages.pdf`
4. Upload `sample_sets/demo_pack/pdf/demo_forged_pages.pdf`

## Recommended Order

### Authentic

- `authentic_01.jpg`
- `authentic_02.jpg`
- `authentic_03.jpg`
- `authentic_04.jpg`

### Forged

- `forged_01.jpg`
- `forged_02.jpg`
- `forged_03.jpg`
- `forged_04.jpg`

## Talking Points

1. The system is optimized for classical image tampering and JPEG-centric forensic analysis.
2. PDF pages are converted to images and analyzed page by page.
3. Confidence and localization outputs help explain the prediction.
4. For the best live result, use prepared JPEG examples instead of random web images.

## Guardrails

1. Do not lead with external random images.
2. Do not claim universal deepfake detection.
3. Use PNG only as a secondary example.
4. If a live random image looks uncertain, switch back to the prepared demo pack.

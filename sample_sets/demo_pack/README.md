# Demo Pack

- Source set: `sample_sets/casia_same_domain_100`
- Selection rule: high-confidence same-domain cases that remain correct after normalization to `.jpg`
- Active release used for selection: `run_20260306_055001`
- Demo images are normalized to `.jpg` for a safer live upload flow.

## Structure

- `selected_good_cases/authentic/`
- `selected_good_cases/forged/`
- `pdf/demo_authentic_pages.pdf`
- `pdf/demo_forged_pages.pdf`
- `demo_manifest.csv`

## Notes

- These files are preselected to make the live image/PDF demo stable.
- Use the prepared `.jpg` files first in the live flow. PNG should be shown only as a secondary example.
- Do not use this pack as a benchmark; it is a curated demo set.

## Authentic Cases

- `authentic_01.jpg`
- `authentic_02.jpg`
- `authentic_03.jpg`
- `authentic_04.jpg`
- `authentic_05.jpg`
- `authentic_06.jpg`
- `authentic_07.jpg`
- `authentic_08.jpg`
- `authentic_09.jpg`
- `authentic_10.jpg`

## Forged Cases

- `forged_01.jpg`
- `forged_02.jpg`
- `forged_03.jpg`
- `forged_04.jpg`
- `forged_05.jpg`
- `forged_06.jpg`
- `forged_07.jpg`
- `forged_08.jpg`
- `forged_09.jpg`
- `forged_10.jpg`

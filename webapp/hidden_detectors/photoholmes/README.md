# PhotoHolmes CPU Sidecar

This sidecar runs real upstream PhotoHolmes methods on CPU and keeps the
existing hidden-detector API contract for CNN fusion.

Runtime notes:
- Sidecar venv is Python `3.11` (`webapp/.venv-photoholmes311`).
- The app runtime remains Python `3.9` (`webapp/.venv-tf`).
- Backend names are kept for compatibility:
  - `noiseprint` (port `8013`) -> PhotoHolmes `Splicebuster`
  - `comprint` (port `8014`) -> PhotoHolmes `Noisesniffer`

Endpoints:
- `GET /health`
- `POST /predict/image`

Response contract:
`ok`, `model_name`, `forged_score`, `label`, `mask_path`, `latency_ms`, `error`.

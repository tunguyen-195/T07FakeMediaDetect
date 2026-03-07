# Hidden MUN Detector

This folder contains the local sidecar integration for the upstream
[MUN](https://github.com/MrHuan3/MUN) forgery detector.

What is committed:
- sidecar server code
- upstream vendored `mmseg` patches required by MUN
- model manifest with download URLs and SHA-256 checksums

What is not committed:
- MUN weights
- NoisePrint++ weights
- `.venv-mun`
- generated masks and logs

Dev workflow on Windows:
1. Run `install.bat`
2. The script creates `.venv-mun`
3. The script downloads weights into `webapp/models/hidden_detectors/mun/weights`
4. Run `start.bat`
5. Django starts only after the hidden detector health check passes on `127.0.0.1:8011`

Runtime contract:
- `GET /health`
- `POST /predict/image`

The sidecar is CPU-first and can use CUDA automatically when available.

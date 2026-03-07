# BenfordRich hidden detector

This sidecar serves the `BenfordRich SVM` runtime from the committed artifacts under `webapp/models/benford_releases/`.

It is the primary handcrafted detector for image and PDF analysis. The webapp calls it locally over HTTP on `127.0.0.1:8012`.

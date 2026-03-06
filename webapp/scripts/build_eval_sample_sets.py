from __future__ import annotations

import csv
import hashlib
import json
import random
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from zipfile import ZipFile


REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_ROOT = REPO_ROOT / "sample_sets"
CASIA_ZIP_PATH = REPO_ROOT / "tmp_eval_source" / "casia" / "casia-20-image-tampering-detection-dataset.zip"
RANDOM_SEED = 42
TARGET_PER_CLASS = 50
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff")

HF_DATASET = "lorenzo-morelli/image-splicing-deepfake-mix"
HF_CONFIG = "default"
HF_SPLIT = "train"
HF_ROWS_API = (
    "https://datasets-server.huggingface.co/rows"
    f"?dataset={HF_DATASET.replace('/', '%2F')}&config={HF_CONFIG}&split={HF_SPLIT}"
    "&offset={offset}&length={length}"
)

AUTHENTIC_KEYWORDS = [
    "genuine and unaltered",
    "original and unedited",
    "no evidence of any manipulation",
    "no signs of digital manipulation",
    "appears to be unmodified",
    "seems to be an original",
    "original and untouched",
    "authentic and untouched",
    "unaltered",
    "unedited photograph",
]

FORGED_KEYWORDS = [
    "fake",
    "tampering",
    "artificially inserted",
    "improperly integrated",
    "introduced from another source",
    "digitally stitched",
    "copied and pasted",
    "added in a splicing operation",
    "traces of manipulation",
    "revealing tampering",
    "was added",
    "was inserted",
    "spliced",
    "manipulated",
]


@dataclass
class SampleRow:
    row_idx: int
    image_url: str
    caption: str
    label: str


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def label_from_caption(caption: str) -> str | None:
    caption_l = caption.lower()
    is_authentic = any(keyword in caption_l for keyword in AUTHENTIC_KEYWORDS)
    is_forged = any(keyword in caption_l for keyword in FORGED_KEYWORDS)
    if is_authentic and not is_forged:
        return "authentic"
    if is_forged and not is_authentic:
        return "forged"
    return None


def fetch_rows(offset: int, length: int) -> list[dict]:
    url = HF_ROWS_API.format(offset=offset, length=length)
    with urllib.request.urlopen(url, timeout=60) as response:
        payload = json.load(response)
    return payload["rows"]


def collect_balanced_hf_rows(target_per_class: int) -> list[SampleRow]:
    authentic: list[SampleRow] = []
    forged: list[SampleRow] = []
    offset = 0
    length = 100

    while len(authentic) < target_per_class or len(forged) < target_per_class:
        rows = fetch_rows(offset=offset, length=length)
        if not rows:
            break

        for row in rows:
            row_idx = row["row_idx"]
            image_url = row["row"]["image"]["src"]
            caption = row["row"]["caption"]
            label = label_from_caption(caption)
            if label is None:
                continue

            sample = SampleRow(
                row_idx=row_idx,
                image_url=image_url,
                caption=caption,
                label=label,
            )
            if label == "authentic" and len(authentic) < target_per_class:
                authentic.append(sample)
            elif label == "forged" and len(forged) < target_per_class:
                forged.append(sample)

            if len(authentic) >= target_per_class and len(forged) >= target_per_class:
                break
        offset += length

    if len(authentic) < target_per_class or len(forged) < target_per_class:
        raise RuntimeError(
            f"Could not collect enough HF rows. authentic={len(authentic)} forged={len(forged)}"
        )

    selected = authentic[:target_per_class] + forged[:target_per_class]
    rng = random.Random(RANDOM_SEED)
    rng.shuffle(selected)
    return selected


def write_manifest(output_root: Path, fieldnames: list[str], rows: list[dict]) -> None:
    manifest_path = output_root / "manifest.csv"
    with manifest_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_metadata(output_root: Path, payload: dict) -> None:
    (output_root / "metadata.json").write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )


def write_readme(output_root: Path, text: str) -> None:
    (output_root / "README.md").write_text(text.strip() + "\n", encoding="utf-8")


def build_casia_sample_set() -> None:
    if not CASIA_ZIP_PATH.exists():
        raise FileNotFoundError(f"CASIA zip missing: {CASIA_ZIP_PATH}")

    output_root = OUTPUT_ROOT / "casia_same_domain_100"
    authentic_dir = output_root / "authentic"
    forged_dir = output_root / "forged"
    authentic_dir.mkdir(parents=True, exist_ok=True)
    forged_dir.mkdir(parents=True, exist_ok=True)

    rng = random.Random(RANDOM_SEED)

    with ZipFile(CASIA_ZIP_PATH) as z:
        names = z.namelist()
        authentic_members = [n for n in names if "/Au/" in n and n.lower().endswith(IMAGE_EXTS)]
        forged_members = [n for n in names if "/Tp/" in n and n.lower().endswith(IMAGE_EXTS)]
        chosen_authentic = rng.sample(authentic_members, TARGET_PER_CLASS)
        chosen_forged = rng.sample(forged_members, TARGET_PER_CLASS)

        manifest_rows: list[dict] = []

        for idx, member in enumerate(chosen_authentic, 1):
            suffix = Path(member).suffix.lower() or ".jpg"
            local_path = authentic_dir / f"authentic_{idx:02d}{suffix}"
            data = z.read(member)
            local_path.write_bytes(data)
            manifest_rows.append(
                {
                    "label": "authentic",
                    "zip_member": member,
                    "local_path": str(local_path),
                    "sha256": sha256_bytes(data),
                }
            )

        for idx, member in enumerate(chosen_forged, 1):
            suffix = Path(member).suffix.lower() or ".jpg"
            local_path = forged_dir / f"forged_{idx:02d}{suffix}"
            data = z.read(member)
            local_path.write_bytes(data)
            manifest_rows.append(
                {
                    "label": "forged",
                    "zip_member": member,
                    "local_path": str(local_path),
                    "sha256": sha256_bytes(data),
                }
            )

    write_manifest(output_root, ["label", "zip_member", "local_path", "sha256"], manifest_rows)
    write_metadata(
        output_root,
        {
            "dataset_name": "CASIA2",
            "sample_type": "same_domain",
            "source": "Kaggle divg07/casia-20-image-tampering-detection-dataset",
            "seed": RANDOM_SEED,
            "per_class": TARGET_PER_CLASS,
            "class_counts": {"authentic": TARGET_PER_CLASS, "forged": TARGET_PER_CLASS},
        },
    )
    write_readme(
        output_root,
        """
# CASIA Same-Domain 100

- Source: `CASIA2` extracted from Kaggle archive `divg07/casia-20-image-tampering-detection-dataset`
- Split: deterministic sample with `seed=42`
- Composition: `50 authentic` from `CASIA2/Au`, `50 forged` from `CASIA2/Tp`
- Purpose: quick same-domain evaluation bundle that matches the main training domain more closely than external web samples
        """,
    )


def download_hf_samples(rows: Iterable[SampleRow], output_root: Path) -> None:
    authentic_dir = output_root / "authentic"
    forged_dir = output_root / "forged"
    authentic_dir.mkdir(parents=True, exist_ok=True)
    forged_dir.mkdir(parents=True, exist_ok=True)

    manifest_rows: list[dict] = []
    counters = {"authentic": 0, "forged": 0}

    for sample in rows:
        counters[sample.label] += 1
        suffix = Path(sample.image_url.split("?")[0]).suffix or ".jpg"
        out_dir = authentic_dir if sample.label == "authentic" else forged_dir
        out_path = out_dir / f"{sample.label}_{counters[sample.label]:02d}_row{sample.row_idx}{suffix}"
        with urllib.request.urlopen(sample.image_url, timeout=120) as response:
            image_bytes = response.read()
        out_path.write_bytes(image_bytes)
        manifest_rows.append(
            {
                "row_idx": sample.row_idx,
                "label": sample.label,
                "caption": sample.caption,
                "source_url": sample.image_url,
                "local_path": str(out_path),
                "sha256": sha256_bytes(image_bytes),
            }
        )

    write_manifest(
        output_root,
        ["row_idx", "label", "caption", "source_url", "local_path", "sha256"],
        manifest_rows,
    )
    write_metadata(
        output_root,
        {
            "dataset_name": HF_DATASET,
            "sample_type": "external",
            "source": "Hugging Face dataset viewer API",
            "seed": RANDOM_SEED,
            "per_class": TARGET_PER_CLASS,
            "class_counts": {"authentic": TARGET_PER_CLASS, "forged": TARGET_PER_CLASS},
            "labeling_method": "caption heuristic",
        },
    )
    write_readme(
        output_root,
        """
# External HF 100

- Source: `lorenzo-morelli/image-splicing-deepfake-mix` via Hugging Face dataset viewer
- Split: deterministic sample with `seed=42`
- Composition: `50 authentic`, `50 forged`
- Labeling: inferred from caption text using keyword heuristics
- Caveat: this set is useful for out-of-domain sanity checks, not as a gold-standard benchmark, because caption-derived labels can contain noise
        """,
    )


def build_external_sample_set() -> None:
    output_root = OUTPUT_ROOT / "external_hf_splicing_mix_100"
    rows = collect_balanced_hf_rows(TARGET_PER_CLASS)
    download_hf_samples(rows, output_root)


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    build_casia_sample_set()
    build_external_sample_set()
    print(f"Sample sets written to {OUTPUT_ROOT}")


if __name__ == "__main__":
    main()

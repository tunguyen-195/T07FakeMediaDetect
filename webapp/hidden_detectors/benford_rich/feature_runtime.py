from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

BENFORD_CHI_SCALE = 1000.0
PATCH_SIZE = 128
BENFORD_METRIC_NAMES = [
    "digit_1",
    "digit_2",
    "digit_3",
    "digit_4",
    "digit_5",
    "digit_6",
    "digit_7",
    "digit_8",
    "digit_9",
    "chi_square_scaled",
    "ks",
    "mad",
    "mse",
]
FEATURE_GROUPS = {
    "benford13_only": [f"gray_global_{name}" for name in BENFORD_METRIC_NAMES],
    "benford_plus_extra": [f"y_global_{name}" for name in BENFORD_METRIC_NAMES]
    + [f"cb_global_{name}" for name in BENFORD_METRIC_NAMES]
    + [f"cr_global_{name}" for name in BENFORD_METRIC_NAMES]
    + [f"gray_laplacian_{name}" for name in BENFORD_METRIC_NAMES]
    + [
        "patch_chi_mean",
        "patch_chi_std",
        "patch_chi_max",
        "patch_chi_p90",
        "patch_ks_mean",
        "patch_ks_std",
        "patch_ks_max",
        "patch_ks_p90",
        "patch_mad_mean",
        "patch_mad_std",
        "patch_mad_max",
        "patch_mad_p90",
        "patch_mse_mean",
        "patch_mse_std",
        "patch_mse_max",
        "patch_mse_p90",
    ],
    "jpeg_blockiness_6": [
        "jpeg_row_boundary_mean",
        "jpeg_row_boundary_std",
        "jpeg_row_boundary_max",
        "jpeg_col_boundary_mean",
        "jpeg_col_boundary_std",
        "jpeg_boundary_ratio",
    ],
    "noise_stats_8": [
        "noise_gauss_mean",
        "noise_gauss_std",
        "noise_gauss_max",
        "noise_gauss_p90",
        "noise_median_mean",
        "noise_median_std",
        "noise_median_max",
        "noise_median_p90",
    ],
    "edge_gradient_8": [
        "edge_sobel_mean",
        "edge_sobel_std",
        "edge_sobel_max",
        "edge_sobel_p90",
        "edge_canny_density",
        "edge_laplacian_variance",
        "edge_boundary_grad_ratio",
        "edge_canny_boundary_ratio",
    ],
    "color_inconsistency_8": [
        "color_cb_std",
        "color_cr_std",
        "color_cb_var",
        "color_cr_var",
        "color_abs_corr_y_cb",
        "color_abs_corr_y_cr",
        "color_abs_corr_cb_cr",
        "color_chroma_to_luma_var_ratio",
    ],
}
FEATURE_GROUPS["benford_plus"] = (
    FEATURE_GROUPS["benford13_only"] + FEATURE_GROUPS["benford_plus_extra"]
)
FEATURE_GROUPS["benford_rich"] = (
    FEATURE_GROUPS["benford_plus"]
    + FEATURE_GROUPS["jpeg_blockiness_6"]
    + FEATURE_GROUPS["noise_stats_8"]
    + FEATURE_GROUPS["edge_gradient_8"]
    + FEATURE_GROUPS["color_inconsistency_8"]
)
FEATURE_WIDTHS = {
    "benford13_only": len(FEATURE_GROUPS["benford13_only"]),
    "benford_plus": len(FEATURE_GROUPS["benford_plus"]),
    "benford_rich": len(FEATURE_GROUPS["benford_rich"]),
}

BENFORD_EXPECTED = np.array(
    [np.log10(1 + 1.0 / d) for d in range(1, 10)], dtype=np.float32
)


def ensure_uint8_gray(channel: np.ndarray) -> np.ndarray:
    if channel.dtype == np.uint8:
        return channel
    arr = np.asarray(channel, dtype=np.float32)
    arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)
    if arr.size == 0:
        return np.zeros((1, 1), dtype=np.uint8)
    min_val = float(arr.min())
    max_val = float(arr.max())
    if max_val <= min_val:
        return np.zeros(arr.shape, dtype=np.uint8)
    scaled = (arr - min_val) / (max_val - min_val)
    return np.clip(np.round(scaled * 255.0), 0, 255).astype(np.uint8)


def resize_if_needed(image_bgr: np.ndarray) -> np.ndarray:
    if image_bgr.shape[0] > 1000:
        return cv2.resize(
            image_bgr, (0, 0), fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA
        )
    return image_bgr


def load_feature_views(image_path: str):
    image_bgr = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image_bgr is None:
        return None
    image_bgr = resize_if_needed(image_bgr)
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    ycrcb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2YCrCb)
    y = ycrcb[:, :, 0]
    cr = ycrcb[:, :, 1]
    cb = ycrcb[:, :, 2]
    lap = cv2.Laplacian(gray, cv2.CV_32F)
    return {
        "bgr": image_bgr,
        "gray": gray,
        "y": y,
        "cb": cb,
        "cr": cr,
        "gray_laplacian": ensure_uint8_gray(np.abs(lap)),
    }


def extract_first_digits_from_dct_array(channel: np.ndarray):
    arr = np.asarray(channel, dtype=np.float32)
    if arr.ndim != 2:
        return []
    h, w = arr.shape
    first_digits = []
    for i in range(0, h - 8, 8):
        for j in range(0, w - 8, 8):
            coeffs = cv2.dct(arr[i : i + 8, j : j + 8]).flatten()[1:]
            for value in coeffs:
                abs_val = abs(float(value))
                if abs_val >= 1:
                    digit = int(str(int(abs_val))[0])
                    if 1 <= digit <= 9:
                        first_digits.append(digit)
    return first_digits


def benford13_from_channel(channel: np.ndarray) -> np.ndarray:
    digits = extract_first_digits_from_dct_array(channel)
    if not digits:
        return np.zeros(13, dtype=np.float32)
    counts = np.array([digits.count(d) for d in range(1, 10)], dtype=np.float32)
    total = float(counts.sum())
    observed = counts / total
    chi_sq = float(np.sum((observed - BENFORD_EXPECTED) ** 2 / BENFORD_EXPECTED) * total)
    ks = float(np.max(np.abs(np.cumsum(observed) - np.cumsum(BENFORD_EXPECTED))))
    mad = float(np.mean(np.abs(observed - BENFORD_EXPECTED)))
    mse = float(np.mean((observed - BENFORD_EXPECTED) ** 2))
    return np.concatenate(
        [observed, np.array([chi_sq / BENFORD_CHI_SCALE, ks, mad, mse], dtype=np.float32)]
    ).astype(np.float32)


def safe_summary(values) -> np.ndarray:
    arr = np.asarray(values, dtype=np.float32)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return np.zeros(4, dtype=np.float32)
    return np.array(
        [
            float(arr.mean()),
            float(arr.std()),
            float(arr.max()),
            float(np.percentile(arr, 90)),
        ],
        dtype=np.float32,
    )


def patch_benford_stats(gray: np.ndarray, patch_size: int = PATCH_SIZE) -> np.ndarray:
    gray = np.asarray(gray, dtype=np.uint8)
    h, w = gray.shape
    if h < patch_size or w < patch_size:
        patches = [gray]
    else:
        patches = [
            gray[y : y + patch_size, x : x + patch_size]
            for y in range(0, h - patch_size + 1, patch_size)
            for x in range(0, w - patch_size + 1, patch_size)
        ] or [gray]
    patch_stats = [benford13_from_channel(patch)[-4:] for patch in patches]
    patch_arr = np.asarray(patch_stats, dtype=np.float32)
    if patch_arr.size == 0:
        return np.zeros(16, dtype=np.float32)
    features = []
    for col_idx in range(4):
        features.extend(safe_summary(patch_arr[:, col_idx]).tolist())
    return np.asarray(features, dtype=np.float32)


def boundary_ratio_from_map(value_map: np.ndarray, step: int = 8) -> float:
    arr = np.asarray(value_map, dtype=np.float32)
    if arr.ndim != 2 or arr.size == 0:
        return 0.0
    row_idx = np.arange(arr.shape[0])
    col_idx = np.arange(arr.shape[1])
    boundary_mask = ((row_idx % step) == (step - 1))[:, None] | (
        (col_idx % step) == (step - 1)
    )[None, :]
    interior_mask = ~boundary_mask
    boundary_vals = arr[boundary_mask]
    interior_vals = arr[interior_mask]
    boundary_mean = float(boundary_vals.mean()) if boundary_vals.size else 0.0
    interior_mean = float(interior_vals.mean()) if interior_vals.size else 0.0
    return float(boundary_mean / (interior_mean + 1e-6))


def jpeg_blockiness_features(gray: np.ndarray) -> np.ndarray:
    gray_f = np.asarray(gray, dtype=np.float32)
    row_diffs = np.abs(np.diff(gray_f, axis=0))
    col_diffs = np.abs(np.diff(gray_f, axis=1))
    row_boundary_idx = np.arange(7, row_diffs.shape[0], 8)
    col_boundary_idx = np.arange(7, col_diffs.shape[1], 8)
    row_boundary_vals = (
        row_diffs[row_boundary_idx, :].mean(axis=1)
        if row_boundary_idx.size
        else np.array([], dtype=np.float32)
    )
    col_boundary_vals = (
        col_diffs[:, col_boundary_idx].mean(axis=0)
        if col_boundary_idx.size
        else np.array([], dtype=np.float32)
    )
    row_non_idx = np.setdiff1d(np.arange(row_diffs.shape[0]), row_boundary_idx)
    col_non_idx = np.setdiff1d(np.arange(col_diffs.shape[1]), col_boundary_idx)
    row_non_vals = (
        row_diffs[row_non_idx, :].mean(axis=1)
        if row_non_idx.size
        else np.array([], dtype=np.float32)
    )
    col_non_vals = (
        col_diffs[:, col_non_idx].mean(axis=0)
        if col_non_idx.size
        else np.array([], dtype=np.float32)
    )
    boundary_sum = (
        float(row_boundary_vals.mean()) if row_boundary_vals.size else 0.0
    ) + (float(col_boundary_vals.mean()) if col_boundary_vals.size else 0.0)
    nonboundary_sum = (
        float(row_non_vals.mean()) if row_non_vals.size else 0.0
    ) + (float(col_non_vals.mean()) if col_non_vals.size else 0.0)
    return np.asarray(
        [
            float(row_boundary_vals.mean()) if row_boundary_vals.size else 0.0,
            float(row_boundary_vals.std()) if row_boundary_vals.size else 0.0,
            float(row_boundary_vals.max()) if row_boundary_vals.size else 0.0,
            float(col_boundary_vals.mean()) if col_boundary_vals.size else 0.0,
            float(col_boundary_vals.std()) if col_boundary_vals.size else 0.0,
            float(boundary_sum / (nonboundary_sum + 1e-6)),
        ],
        dtype=np.float32,
    )


def noise_stats_features(gray: np.ndarray) -> np.ndarray:
    gray_f = np.asarray(gray, dtype=np.float32)
    gauss = cv2.GaussianBlur(gray_f, (5, 5), 0)
    median = cv2.medianBlur(np.asarray(gray, dtype=np.uint8), 5).astype(np.float32)
    return np.concatenate(
        [
            safe_summary(np.abs(gray_f - gauss).reshape(-1)),
            safe_summary(np.abs(gray_f - median).reshape(-1)),
        ]
    ).astype(np.float32)


def edge_gradient_features(gray: np.ndarray) -> np.ndarray:
    gray_f = np.asarray(gray, dtype=np.float32)
    sobel_x = cv2.Sobel(gray_f, cv2.CV_32F, 1, 0, ksize=3)
    sobel_y = cv2.Sobel(gray_f, cv2.CV_32F, 0, 1, ksize=3)
    sobel_mag = np.sqrt((sobel_x ** 2) + (sobel_y ** 2))
    canny = cv2.Canny(np.asarray(gray, dtype=np.uint8), 100, 200)
    lap_var = float(cv2.Laplacian(np.asarray(gray, dtype=np.uint8), cv2.CV_64F).var())
    return np.asarray(
        [
            float(sobel_mag.mean()),
            float(sobel_mag.std()),
            float(sobel_mag.max()) if sobel_mag.size else 0.0,
            float(np.percentile(sobel_mag, 90)) if sobel_mag.size else 0.0,
            float((canny > 0).mean()),
            lap_var,
            boundary_ratio_from_map(sobel_mag, step=8),
            boundary_ratio_from_map(canny.astype(np.float32), step=8),
        ],
        dtype=np.float32,
    )


def safe_abs_corr(a: np.ndarray, b: np.ndarray) -> float:
    a_flat = np.asarray(a, dtype=np.float32).reshape(-1)
    b_flat = np.asarray(b, dtype=np.float32).reshape(-1)
    if a_flat.size == 0 or b_flat.size == 0:
        return 0.0
    if float(a_flat.std()) < 1e-6 or float(b_flat.std()) < 1e-6:
        return 0.0
    corr = np.corrcoef(a_flat, b_flat)[0, 1]
    if not np.isfinite(corr):
        return 0.0
    return float(abs(corr))


def color_inconsistency_features(y: np.ndarray, cb: np.ndarray, cr: np.ndarray) -> np.ndarray:
    y_f = np.asarray(y, dtype=np.float32)
    cb_f = np.asarray(cb, dtype=np.float32)
    cr_f = np.asarray(cr, dtype=np.float32)
    return np.asarray(
        [
            float(cb_f.std()),
            float(cr_f.std()),
            float(cb_f.var()),
            float(cr_f.var()),
            safe_abs_corr(y_f, cb_f),
            safe_abs_corr(y_f, cr_f),
            safe_abs_corr(cb_f, cr_f),
            float((cb_f.var() + cr_f.var()) / (y_f.var() + 1e-6)),
        ],
        dtype=np.float32,
    )


def extract_feature_sets(image_path: str):
    views = load_feature_views(image_path)
    if views is None:
        return {
            "benford13_only": np.zeros(FEATURE_WIDTHS["benford13_only"], dtype=np.float32),
            "benford_plus": np.zeros(FEATURE_WIDTHS["benford_plus"], dtype=np.float32),
            "benford_rich": np.zeros(FEATURE_WIDTHS["benford_rich"], dtype=np.float32),
        }
    gray13 = benford13_from_channel(views["gray"])
    y13 = benford13_from_channel(views["y"])
    cb13 = benford13_from_channel(views["cb"])
    cr13 = benford13_from_channel(views["cr"])
    lap13 = benford13_from_channel(views["gray_laplacian"])
    patch16 = patch_benford_stats(views["gray"], patch_size=PATCH_SIZE)
    benford13 = gray13.astype(np.float32)
    benford_plus = np.concatenate([gray13, y13, cb13, cr13, lap13, patch16]).astype(
        np.float32
    )
    benford_rich = np.concatenate(
        [
            benford_plus,
            jpeg_blockiness_features(views["gray"]),
            noise_stats_features(views["gray"]),
            edge_gradient_features(views["gray"]),
            color_inconsistency_features(views["y"], views["cb"], views["cr"]),
        ]
    ).astype(np.float32)
    return {
        "benford13_only": np.nan_to_num(benford13, nan=0.0, posinf=0.0, neginf=0.0),
        "benford_plus": np.nan_to_num(benford_plus, nan=0.0, posinf=0.0, neginf=0.0),
        "benford_rich": np.nan_to_num(benford_rich, nan=0.0, posinf=0.0, neginf=0.0),
    }

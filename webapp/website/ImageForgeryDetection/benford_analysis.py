"""
Benford feature extraction and contract helpers for hybrid image forgery detection.
"""

import numpy as np
import cv2
from scipy import stats

# Shared feature contract used by training and inference.
FEATURE_SCHEMA_VERSION = "hybrid_v2"
COMPATIBLE_FEATURE_SCHEMA_VERSIONS = [
    "hybrid_v2",
    "hybrid_v3_casia_columbia",
]
LABEL_MAPPING = {"authentic": 0, "forged": 1}
CNN_SCORE_SEMANTICS = "p_forged = 1 - p_authentic"
BENFORD_CHI_SCALE = 1000.0
BENFORD_FEATURE_ORDER = [
    "benford_digit_1",
    "benford_digit_2",
    "benford_digit_3",
    "benford_digit_4",
    "benford_digit_5",
    "benford_digit_6",
    "benford_digit_7",
    "benford_digit_8",
    "benford_digit_9",
    "benford_chi_square_scaled",
    "benford_ks",
    "benford_mad",
    "benford_mse",
]
HYBRID_FEATURE_ORDER = ["cnn_p_forged", *BENFORD_FEATURE_ORDER]

BENFORD_DISTRIBUTION = {d: np.log10(1 + 1 / d) for d in range(1, 10)}


def get_feature_contract():
    """Return the expected hybrid feature contract for metadata validation."""
    return {
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "label_mapping": LABEL_MAPPING.copy(),
        "cnn_score_semantics": CNN_SCORE_SEMANTICS,
        "benford_chi_scale": BENFORD_CHI_SCALE,
        "hybrid_feature_order": HYBRID_FEATURE_ORDER.copy(),
        "benford_feature_order": BENFORD_FEATURE_ORDER.copy(),
    }


def get_compatible_feature_schema_versions():
    """Return schema versions accepted by the webapp runtime."""
    return COMPATIBLE_FEATURE_SCHEMA_VERSIONS.copy()


def get_benford_expected():
    """Return Benford expected first-digit distribution."""
    return BENFORD_DISTRIBUTION.copy()


def extract_first_digits_from_pixels(image_array):
    """Extract first digits from non-zero pixel values."""
    flat_pixels = image_array.flatten()
    first_digits = []

    for pixel in flat_pixels:
        if pixel > 0:
            first_digit = int(str(int(pixel))[0])
            if 1 <= first_digit <= 9:
                first_digits.append(first_digit)

    return first_digits


def extract_first_digits_from_dct(image_path):
    """
    Extract first digits from DCT coefficients.

    This intentionally matches training behavior:
    - grayscale image
    - resize by 0.5 if height > 1000
    - float32 values
    - non-padded 8x8 blocks
    - skip DC coefficient
    """
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return []

    if img.shape[0] > 1000:
        img = cv2.resize(img, (0, 0), fx=0.5, fy=0.5)

    img = np.float32(img)
    h, w = img.shape
    first_digits = []

    for i in range(0, h - 8, 8):
        for j in range(0, w - 8, 8):
            block = img[i : i + 8, j : j + 8]
            dct_block = cv2.dct(block)
            coeffs = dct_block.flatten()[1:]

            for val in coeffs:
                abs_val = abs(val)
                if abs_val >= 1:
                    first_digit = int(str(int(abs_val))[0])
                    if 1 <= first_digit <= 9:
                        first_digits.append(first_digit)

    return first_digits


def calculate_observed_distribution(first_digits):
    """Compute observed first-digit distribution for digits 1..9."""
    total = len(first_digits)
    if total == 0:
        return {d: 0 for d in range(1, 10)}

    return {d: first_digits.count(d) / total for d in range(1, 10)}


def chi_square_test(observed, expected, n):
    """Run chi-square goodness-of-fit test against Benford distribution."""
    chi_sq = 0
    for d in range(1, 10):
        e = expected[d] * n
        o = observed.get(d, 0) * n
        if e > 0:
            chi_sq += ((o - e) ** 2) / e

    p_value = 1 - stats.chi2.cdf(chi_sq, 8)
    return chi_sq, p_value


def kolmogorov_smirnov_test(first_digits):
    """Run KS-like CDF distance test for first-digit distribution."""
    if len(first_digits) == 0:
        return 1.0, 0.0

    benford_cdf = np.cumsum([BENFORD_DISTRIBUTION[d] for d in range(1, 10)])

    total = len(first_digits)
    observed_counts = [first_digits.count(d) / total for d in range(1, 10)]
    observed_cdf = np.cumsum(observed_counts)

    ks_stat = np.max(np.abs(observed_cdf - benford_cdf))

    n = len(first_digits)
    p_value = 2 * np.exp(-2 * n * ks_stat**2)
    return ks_stat, p_value


def benford_divergence(first_digits):
    """Compute divergence metrics against Benford distribution."""
    if len(first_digits) == 0:
        return {
            "chi_square": float("inf"),
            "ks_statistic": 1.0,
            "mad": 1.0,
            "mse": 1.0,
        }

    observed = calculate_observed_distribution(first_digits)
    expected = get_benford_expected()
    n = len(first_digits)

    chi_sq, chi_p = chi_square_test(observed, expected, n)
    ks_stat, ks_p = kolmogorov_smirnov_test(first_digits)
    mad = np.mean([abs(observed.get(d, 0) - expected[d]) for d in range(1, 10)])
    mse = np.mean([(observed.get(d, 0) - expected[d]) ** 2 for d in range(1, 10)])

    return {
        "chi_square": chi_sq,
        "chi_p_value": chi_p,
        "ks_statistic": ks_stat,
        "ks_p_value": ks_p,
        "mad": mad,
        "mse": mse,
        "n_samples": n,
    }


def extract_benford_features(image_path):
    """
    Return 13 Benford features in canonical order:
    [d1..d9, chi_scaled, ks, mad, mse]
    """
    dct_digits = extract_first_digits_from_dct(image_path)
    if len(dct_digits) == 0:
        return np.zeros(13)

    observed = calculate_observed_distribution(dct_digits)
    divergence = benford_divergence(dct_digits)

    features = [observed.get(d, 0) for d in range(1, 10)]
    features.append(divergence["chi_square"] / BENFORD_CHI_SCALE)
    features.append(divergence["ks_statistic"])
    features.append(divergence["mad"])
    features.append(divergence["mse"])

    return np.array(features)


def analyze_benford(image_path, threshold_chi=15.51, threshold_ks=0.05):
    """Return human-readable Benford analysis for the forensic UI."""
    dct_digits = extract_first_digits_from_dct(image_path)
    divergence = benford_divergence(dct_digits)

    is_suspicious = (
        divergence["chi_square"] > threshold_chi
        or divergence["ks_p_value"] < threshold_ks
    )

    if divergence["chi_square"] < threshold_chi:
        confidence = 100 - (divergence["chi_square"] / threshold_chi * 50)
    else:
        confidence = max(0, 50 - (divergence["chi_square"] - threshold_chi) / 2)

    return {
        "is_suspicious": is_suspicious,
        "is_authentic": not is_suspicious,
        "confidence": round(max(0, min(100, confidence)), 2),
        "chi_square": round(divergence["chi_square"], 4),
        "chi_p_value": round(divergence.get("chi_p_value", 0), 4),
        "ks_statistic": round(divergence["ks_statistic"], 4),
        "ks_p_value": round(divergence.get("ks_p_value", 0), 4),
        "mad": round(divergence["mad"], 4),
        "n_samples": divergence["n_samples"],
        "observed_distribution": calculate_observed_distribution(dct_digits),
        "expected_distribution": get_benford_expected(),
    }


def plot_benford_comparison(first_digits, save_path=None):
    """Plot observed-vs-expected first-digit frequencies."""
    import matplotlib.pyplot as plt

    observed = calculate_observed_distribution(first_digits)
    expected = get_benford_expected()

    digits = list(range(1, 10))
    obs_vals = [observed.get(d, 0) for d in digits]
    exp_vals = [expected[d] for d in digits]

    x = np.arange(len(digits))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(x - width / 2, obs_vals, width, label="Observed", color="steelblue")
    ax.bar(x + width / 2, exp_vals, width, label="Benford Expected", color="coral")

    ax.set_xlabel("First Digit", fontsize=12)
    ax.set_ylabel("Frequency", fontsize=12)
    ax.set_title("Benford's Law Analysis", fontsize=14, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(digits)
    ax.legend()
    ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")

    return fig


# Backward-compat alias.
benford_analysis = analyze_benford

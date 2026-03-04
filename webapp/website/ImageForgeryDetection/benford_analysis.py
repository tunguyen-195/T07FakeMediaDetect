"""
Benford's Law Analysis Module for Image Forgery Detection
Author: T07FakeMediaDetect Team
Description: Phân tích ảnh dựa trên Luật Benford để phát hiện giả mạo
"""

import numpy as np
from PIL import Image
import cv2
from scipy import stats

# Phân phối lý thuyết của Luật Benford
BENFORD_DISTRIBUTION = {d: np.log10(1 + 1/d) for d in range(1, 10)}


def get_benford_expected():
    """
    Trả về phân phối kỳ vọng theo Luật Benford
    
    Returns:
        dict: Xác suất của mỗi chữ số đầu tiên (1-9)
    """
    return BENFORD_DISTRIBUTION.copy()


def extract_first_digits_from_pixels(image_array):
    """
    Trích xuất chữ số đầu tiên từ các giá trị pixel
    
    Parameters:
        image_array: numpy array của ảnh
        
    Returns:
        list: Danh sách các chữ số đầu tiên
    """
    flat_pixels = image_array.flatten()
    first_digits = []
    
    for pixel in flat_pixels:
        if pixel > 0:
            # Lấy chữ số đầu tiên
            first_digit = int(str(int(pixel))[0])
            if 1 <= first_digit <= 9:
                first_digits.append(first_digit)
    
    return first_digits


def extract_first_digits_from_dct(image_path):
    """
    Trích xuất chữ số đầu tiên từ hệ số DCT (cho ảnh JPEG)
    
    Parameters:
        image_path: Đường dẫn đến ảnh
        
    Returns:
        list: Danh sách các chữ số đầu tiên từ DCT coefficients
    """
    # Đọc ảnh grayscale
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return []
    
    # Áp dụng DCT trên từng khối 8x8
    h, w = img.shape
    first_digits = []
    
    # Padding để chia hết cho 8
    h_pad = (8 - h % 8) % 8
    w_pad = (8 - w % 8) % 8
    img_padded = np.pad(img, ((0, h_pad), (0, w_pad)), mode='constant')
    
    # Duyệt qua từng khối 8x8
    for i in range(0, img_padded.shape[0], 8):
        for j in range(0, img_padded.shape[1], 8):
            block = img_padded[i:i+8, j:j+8].astype(np.float32)
            dct_block = cv2.dct(block)
            
            for val in dct_block.flatten():
                abs_val = abs(val)
                if abs_val >= 1:
                    first_digit = int(str(int(abs_val))[0])
                    if 1 <= first_digit <= 9:
                        first_digits.append(first_digit)
    
    return first_digits


def calculate_observed_distribution(first_digits):
    """
    Tính phân phối quan sát được từ danh sách chữ số đầu tiên
    
    Parameters:
        first_digits: Danh sách các chữ số đầu tiên
        
    Returns:
        dict: Tần suất của mỗi chữ số (1-9)
    """
    total = len(first_digits)
    if total == 0:
        return {d: 0 for d in range(1, 10)}
    
    observed = {d: first_digits.count(d) / total for d in range(1, 10)}
    return observed


def chi_square_test(observed, expected, n):
    """
    Thực hiện kiểm định Chi-square
    
    Parameters:
        observed: dict phân phối quan sát
        expected: dict phân phối kỳ vọng
        n: số mẫu
        
    Returns:
        tuple: (chi_square_stat, p_value)
    """
    chi_sq = 0
    for d in range(1, 10):
        e = expected[d] * n
        o = observed.get(d, 0) * n
        if e > 0:
            chi_sq += ((o - e) ** 2) / e
    
    # Degrees of freedom = 8 (9 categories - 1)
    p_value = 1 - stats.chi2.cdf(chi_sq, 8)
    
    return chi_sq, p_value


def kolmogorov_smirnov_test(first_digits):
    """
    Thực hiện kiểm định Kolmogorov-Smirnov
    
    Parameters:
        first_digits: Danh sách các chữ số đầu tiên
        
    Returns:
        tuple: (ks_stat, p_value)
    """
    if len(first_digits) == 0:
        return 1.0, 0.0
    
    # Tạo CDF của Benford
    benford_cdf = np.cumsum([BENFORD_DISTRIBUTION[d] for d in range(1, 10)])
    
    # Tạo CDF quan sát được
    total = len(first_digits)
    observed_counts = [first_digits.count(d) / total for d in range(1, 10)]
    observed_cdf = np.cumsum(observed_counts)
    
    # Tính KS statistic
    ks_stat = np.max(np.abs(observed_cdf - benford_cdf))
    
    # Xấp xỉ p-value
    n = len(first_digits)
    p_value = 2 * np.exp(-2 * n * ks_stat ** 2)
    
    return ks_stat, p_value


def benford_divergence(first_digits):
    """
    Tính độ lệch so với phân phối Benford sử dụng nhiều metrics
    
    Parameters:
        first_digits: Danh sách các chữ số đầu tiên
        
    Returns:
        dict: Các metrics đánh giá độ lệch
    """
    if len(first_digits) == 0:
        return {
            'chi_square': float('inf'),
            'ks_statistic': 1.0,
            'mad': 1.0,  # Mean Absolute Deviation
            'mse': 1.0,  # Mean Square Error
        }
    
    observed = calculate_observed_distribution(first_digits)
    expected = get_benford_expected()
    n = len(first_digits)
    
    # Chi-square
    chi_sq, chi_p = chi_square_test(observed, expected, n)
    
    # KS test
    ks_stat, ks_p = kolmogorov_smirnov_test(first_digits)
    
    # MAD (Mean Absolute Deviation)
    mad = np.mean([abs(observed.get(d, 0) - expected[d]) for d in range(1, 10)])
    
    # MSE (Mean Square Error)
    mse = np.mean([(observed.get(d, 0) - expected[d]) ** 2 for d in range(1, 10)])
    
    return {
        'chi_square': chi_sq,
        'chi_p_value': chi_p,
        'ks_statistic': ks_stat,
        'ks_p_value': ks_p,
        'mad': mad,
        'mse': mse,
        'n_samples': n
    }


def extract_benford_features(image_path):
    """
    Trích xuất các features dựa trên Luật Benford cho machine learning
    
    Parameters:
        image_path: Đường dẫn đến ảnh
        
    Returns:
        numpy array: Vector features (9 observed frequencies + 4 divergence metrics)
    """
    # Trích xuất từ DCT
    dct_digits = extract_first_digits_from_dct(image_path)
    
    if len(dct_digits) == 0:
        return np.zeros(13)
    
    # Tính observed distribution
    observed = calculate_observed_distribution(dct_digits)
    
    # Tính divergence metrics
    divergence = benford_divergence(dct_digits)
    
    # Tạo feature vector
    features = []
    
    # 9 observed frequencies
    for d in range(1, 10):
        features.append(observed.get(d, 0))
    
    # 4 divergence metrics
    features.append(divergence['chi_square'] / 100)  # Normalize
    features.append(divergence['ks_statistic'])
    features.append(divergence['mad'])
    features.append(divergence['mse'])
    
    return np.array(features)


def analyze_benford(image_path, threshold_chi=15.51, threshold_ks=0.05):
    """
    Phân tích ảnh dựa trên Luật Benford
    
    Parameters:
        image_path: Đường dẫn đến ảnh
        threshold_chi: Ngưỡng chi-square (df=8, alpha=0.05 là 15.51)
        threshold_ks: Ngưỡng p-value cho KS test
        
    Returns:
        dict: Kết quả phân tích
    """
    # Trích xuất chữ số đầu tiên từ DCT
    dct_digits = extract_first_digits_from_dct(image_path)
    
    # Tính các metrics
    divergence = benford_divergence(dct_digits)
    
    # Đánh giá
    is_suspicious = (
        divergence['chi_square'] > threshold_chi or 
        divergence['ks_p_value'] < threshold_ks
    )
    
    # Tính confidence score
    if divergence['chi_square'] < threshold_chi:
        confidence = 100 - (divergence['chi_square'] / threshold_chi * 50)
    else:
        confidence = max(0, 50 - (divergence['chi_square'] - threshold_chi) / 2)
    
    return {
        'is_suspicious': is_suspicious,
        'is_authentic': not is_suspicious,
        'confidence': round(max(0, min(100, confidence)), 2),
        'chi_square': round(divergence['chi_square'], 4),
        'chi_p_value': round(divergence.get('chi_p_value', 0), 4),
        'ks_statistic': round(divergence['ks_statistic'], 4),
        'ks_p_value': round(divergence.get('ks_p_value', 0), 4),
        'mad': round(divergence['mad'], 4),
        'n_samples': divergence['n_samples'],
        'observed_distribution': calculate_observed_distribution(dct_digits),
        'expected_distribution': get_benford_expected()
    }


def plot_benford_comparison(first_digits, save_path=None):
    """
    Vẽ biểu đồ so sánh phân phối quan sát với Luật Benford
    
    Parameters:
        first_digits: Danh sách chữ số đầu tiên
        save_path: Đường dẫn lưu hình (optional)
        
    Returns:
        matplotlib Figure object
    """
    import matplotlib.pyplot as plt
    
    observed = calculate_observed_distribution(first_digits)
    expected = get_benford_expected()
    
    digits = list(range(1, 10))
    obs_vals = [observed.get(d, 0) for d in digits]
    exp_vals = [expected[d] for d in digits]
    
    x = np.arange(len(digits))
    width = 0.35
    
    fig, ax = plt.subplots(figsize=(10, 6))
    bars1 = ax.bar(x - width/2, obs_vals, width, label='Observed', color='steelblue')
    bars2 = ax.bar(x + width/2, exp_vals, width, label='Benford Expected', color='coral')
    
    ax.set_xlabel('First Digit', fontsize=12)
    ax.set_ylabel('Frequency', fontsize=12)
    ax.set_title("Benford's Law Analysis", fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(digits)
    ax.legend()
    ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
    
    return fig


# Alias for backward compatibility
benford_analysis = analyze_benford

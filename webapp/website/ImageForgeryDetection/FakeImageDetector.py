import os
import json
import ctypes
import shutil
import tempfile
import sys

try:
    from keras.models import load_model  # type: ignore
except Exception:
    load_model = None

import numpy as np
import h5py
from PIL import Image, ImageChops, ImageEnhance, ImageFilter
import cv2 as cv
from matplotlib import pyplot as plt
from website.ImageForgeryDetection.NeuralNets import initClassifier, initSegmenter
from skimage import feature
import joblib

try:
    import sklearn
except Exception:
    sklearn = None

from website.ImageForgeryDetection.fusion import (
    build_current_only_result,
    fuse_detector_votes,
)
from website.ImageForgeryDetection.benford_rich_client import (
    predict_benford_rich,
)
from website.ImageForgeryDetection.hidden_detector_client import (
    create_request_id,
    predict_hidden_detector,
)


def safe_print(*args, **kwargs):
    sep = kwargs.pop("sep", " ")
    end = kwargs.pop("end", "\n")
    target_streams = []
    if "file" in kwargs:
        target_streams.append(kwargs.pop("file"))
    target_streams.extend(
        [
            sys.stdout,
            getattr(sys, "__stdout__", None),
            sys.stderr,
            getattr(sys, "__stderr__", None),
        ]
    )
    text = sep.join(str(arg) for arg in args)
    if end is not None:
        text += end
    for stream in target_streams:
        if stream is None:
            continue
        try:
            stream.write(text)
            stream.flush()
            return
        except Exception:
            continue

# Import Benford module + feature contract
try:
    from website.ImageForgeryDetection.benford_analysis import (
        extract_benford_features,
        get_feature_contract,
        get_compatible_feature_schema_versions,
        HYBRID_FEATURE_ORDER,
    )
except Exception:
    safe_print("Warning: benford_analysis module not found. Hybrid mode unavailable.")
    extract_benford_features = None

    def get_feature_contract():
        return {
            "feature_schema_version": "hybrid_v2",
            "label_mapping": {"authentic": 0, "forged": 1},
            "cnn_score_semantics": "p_forged = 1 - p_authentic",
            "benford_chi_scale": 1000.0,
            "hybrid_feature_order": [
                "cnn_p_forged",
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
            ],
            "benford_feature_order": [
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
            ],
        }

    def get_compatible_feature_schema_versions():
        return ["hybrid_v2", "hybrid_v3_casia_columbia"]

    HYBRID_FEATURE_ORDER = get_feature_contract()["hybrid_feature_order"]

# Color-image denoising (kept for backward compatibility)
from skimage.restoration import (denoise_wavelet, estimate_sigma)
from skimage.util import random_noise
import skimage.io

resaved_filename = os.path.join(os.getcwd(), "media", "tempresaved.jpg")
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MODELS_ROOT = os.path.join(PROJECT_ROOT, "models")

# Canonical model artifact paths (do not use old-model folders in runtime).
DEFAULT_MODEL_PATH = os.path.join(MODELS_ROOT, "proposed_ela_50_casia_fidac.h5")
DEFAULT_SEGMENTER_WEIGHTS = os.path.join(MODELS_ROOT, "segmenter_weights.h5")
DEFAULT_SVM_PATH = os.path.join(MODELS_ROOT, "hybrid_svm_model.pkl")
DEFAULT_SCALER_PATH = os.path.join(MODELS_ROOT, "hybrid_scaler.pkl")
DEFAULT_METADATA_PATH = os.path.join(MODELS_ROOT, "hybrid_metadata.json")
ACTIVE_RELEASE_PATH = os.path.join(MODELS_ROOT, "active_release.json")


def resolve_primary_detector_mode(environ=None):
    env = environ if environ is not None else os.environ
    explicit_mode = str(env.get("T07_PRIMARY_IMAGE_DETECTOR", "")).strip().lower()
    if explicit_mode:
        if explicit_mode in {"cnn_only", "legacy_current", "benford_rich"}:
            return explicit_mode
        safe_print(
            f"Warning: unsupported T07_PRIMARY_IMAGE_DETECTOR={explicit_mode}. "
            "Falling back to cnn_only."
        )
        return "cnn_only"

    if str(env.get("T07_USE_BENFORD_RICH_PRIMARY", "0")).strip() == "1":
        return "benford_rich"

    return "cnn_only"


PRIMARY_DETECTOR_MODE = resolve_primary_detector_mode()
DEFAULT_LEGACY_ARTIFACTS = {
    "release_id": "legacy_canonical",
    "bundle_source": "legacy",
    "cnn_model_path": DEFAULT_MODEL_PATH,
    "svm_model_path": DEFAULT_SVM_PATH,
    "scaler_path": DEFAULT_SCALER_PATH,
    "metadata_path": DEFAULT_METADATA_PATH,
    "metrics_path": None,
    "run_summary_path": None,
}


class FID:

    def prepare_image(self, fname):
        image_size = (128, 128)
        return np.array(self.convert_to_ela_image(fname, 90).resize(image_size)).flatten() / 255.0

    def _resolve_models_path(self, path_value):
        if not path_value:
            return None
        if os.path.isabs(path_value):
            return path_value
        return os.path.join(MODELS_ROOT, path_value)

    def _get_legacy_artifact_manifest(self):
        return dict(DEFAULT_LEGACY_ARTIFACTS)

    def _load_active_release_manifest(self):
        if not os.path.exists(ACTIVE_RELEASE_PATH):
            return None

        with open(ACTIVE_RELEASE_PATH, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        required_keys = [
            "release_id",
            "cnn_model_path",
            "svm_model_path",
            "scaler_path",
            "metadata_path",
            "metrics_path",
            "run_summary_path",
            "activated_at",
        ]
        missing = [k for k in required_keys if not manifest.get(k)]
        if missing:
            raise ValueError(f"active_release.json missing keys: {missing}")

        resolved = dict(manifest)
        for key in [
            "cnn_model_path",
            "svm_model_path",
            "scaler_path",
            "metadata_path",
            "metrics_path",
            "run_summary_path",
        ]:
            resolved[key] = self._resolve_models_path(manifest[key])

        missing_files = [
            key for key in [
                "cnn_model_path",
                "svm_model_path",
                "scaler_path",
                "metadata_path",
                "metrics_path",
                "run_summary_path",
            ]
            if not os.path.exists(resolved[key])
        ]
        if missing_files:
            raise FileNotFoundError(
                f"Active release files missing: {missing_files}"
            )

        resolved["bundle_source"] = "active"
        return resolved

    def _get_preferred_artifact_manifest(self):
        try:
            manifest = self._load_active_release_manifest()
            if manifest:
                safe_print(
                    f"Using active release: {manifest['release_id']} "
                    f"(CNN={os.path.basename(manifest['cnn_model_path'])})"
                )
                return manifest
        except Exception as e:
            safe_print(f"Active release unavailable: {e}. Falling back to legacy runtime.")

        manifest = self._get_legacy_artifact_manifest()
        safe_print(
            f"Using legacy runtime: {manifest['release_id']} "
            f"(CNN={os.path.basename(manifest['cnn_model_path'])})"
        )
        return manifest

    def _load_cnn_model(self, manifest):
        model_path = manifest["cnn_model_path"]
        if load_model is None:
            raise RuntimeError("keras.models.load_model unavailable")
        if not model_path or not os.path.exists(model_path):
            raise FileNotFoundError(f"CNN model not found: {model_path}")
        try:
            return load_model(model_path, compile=False)
        except Exception as e:
            error_text = str(e)
            if "batch_shape" not in error_text and "DTypePolicy" not in error_text:
                raise

            compat_model_path = self._ensure_compatible_cnn_model(model_path)
            safe_print(
                "Using runtime-compatible CNN copy: "
                f"{os.path.basename(compat_model_path)}"
            )
            return load_model(compat_model_path, compile=False)

    def _run_cnn_inference(self, fname, manifest):
        model = self._load_cnn_model(manifest)
        test_image = self.prepare_image(fname)
        test_image = test_image.reshape(-1, 128, 128, 3)
        y_pred = model.predict(test_image)

        # CNN output convention from IFAKE notebook:
        # y_pred ~ p_authentic where Authentic=1, Forged=0
        p_authentic = float(y_pred[0][0])
        p_forged = 1.0 - p_authentic

        safe_print(
            f"CNN bundle={manifest['release_id']} "
            f"file={os.path.basename(manifest['cnn_model_path'])}"
        )
        safe_print(
            f"CNN Raw Output: p_authentic={p_authentic:.6f}, "
            f"p_forged={p_forged:.6f}"
        )
        return p_authentic, p_forged

    def _run_legacy_current_detector(self, fname):
        active_manifest = self._get_preferred_artifact_manifest()
        runtime_manifest = active_manifest

        try:
            p_authentic, p_forged = self._run_cnn_inference(fname, runtime_manifest)
        except Exception as e:
            safe_print(
                f"Preferred CNN bundle failed: {runtime_manifest['release_id']} ({e}). "
                "Trying legacy runtime."
            )
            runtime_manifest = self._get_legacy_artifact_manifest()
            try:
                p_authentic, p_forged = self._run_cnn_inference(fname, runtime_manifest)
            except Exception as legacy_e:
                raise RuntimeError(f"Legacy CNN fallback failed: {legacy_e}") from legacy_e

        if extract_benford_features:
            try:
                safe_print("=== RUNNING HYBRID ANALYSIS (CNN + BENFORD) ===")
                svm, scaler, metadata = self._load_hybrid_components(runtime_manifest)

                benford_feats = extract_benford_features(fname)
                combined_features = np.hstack(([p_forged], benford_feats)).reshape(1, -1)

                if combined_features.shape[1] != len(HYBRID_FEATURE_ORDER):
                    raise ValueError(
                        f"Hybrid feature width mismatch: got={combined_features.shape[1]} expected={len(HYBRID_FEATURE_ORDER)}"
                    )

                safe_print(
                    f"Hybrid features shape={combined_features.shape}, feature_schema={metadata['feature_schema_version']}"
                )

                scaled_features = scaler.transform(combined_features)
                svm_probs = svm.predict_proba(scaled_features)[0]
                prob_forged = float(svm_probs[1])
                prediction = "Forged" if prob_forged > 0.5 else "Authentic"
                confidence = prob_forged if prediction == "Forged" else (1.0 - prob_forged)

                safe_print(f"Hybrid SVM Prob (Forged): {prob_forged:.6f}")
                safe_print(f"Hybrid Result: {prediction} ({confidence * 100:0.2f}%)")
                return {
                    "score_forged": prob_forged,
                    "label": prediction,
                    "confidence": round(confidence * 100.0, 2),
                    "source": "hybrid",
                    "release_id": runtime_manifest["release_id"],
                }

            except Exception as e:
                safe_print(
                    f"Hybrid unavailable for bundle {runtime_manifest['release_id']}: {e}."
                )
                if runtime_manifest.get("bundle_source") != "legacy":
                    safe_print("Trying legacy runtime bundle for full fallback.")
                    legacy_manifest = self._get_legacy_artifact_manifest()
                    try:
                        p_authentic, p_forged = self._run_cnn_inference(fname, legacy_manifest)
                        svm, scaler, metadata = self._load_hybrid_components(legacy_manifest)
                        benford_feats = extract_benford_features(fname)
                        combined_features = np.hstack(([p_forged], benford_feats)).reshape(1, -1)
                        if combined_features.shape[1] != len(HYBRID_FEATURE_ORDER):
                            raise ValueError(
                                f"Hybrid feature width mismatch: got={combined_features.shape[1]} expected={len(HYBRID_FEATURE_ORDER)}"
                            )

                        scaled_features = scaler.transform(combined_features)
                        svm_probs = svm.predict_proba(scaled_features)[0]
                        prob_forged = float(svm_probs[1])
                        prediction = "Forged" if prob_forged > 0.5 else "Authentic"
                        confidence = prob_forged if prediction == "Forged" else (1.0 - prob_forged)

                        safe_print(f"Legacy hybrid Result: {prediction} ({confidence * 100:0.2f}%)")
                        return {
                            "score_forged": prob_forged,
                            "label": prediction,
                            "confidence": round(confidence * 100.0, 2),
                            "source": "hybrid",
                            "release_id": legacy_manifest["release_id"],
                        }
                    except Exception as legacy_e:
                        safe_print(
                            f"Legacy hybrid fallback unavailable: {legacy_e}. "
                            "Falling back to CNN-only."
                        )

        safe_print("=== FALLBACK TO CNN ONLY ===")
        prediction = "Forged" if p_authentic <= 0.5 else "Authentic"
        confidence = (1.0 - p_authentic) if prediction == "Forged" else p_authentic
        safe_print(f"CNN Result: {prediction} ({confidence * 100:0.2f}%)")
        return {
            "score_forged": float(p_forged),
            "label": prediction,
            "confidence": round(confidence * 100.0, 2),
            "source": "cnn_only",
            "release_id": runtime_manifest["release_id"],
        }

    def _run_benford_rich_detector(self, fname, source_type="image"):
        response = predict_benford_rich(fname, source_type=source_type)
        safe_print(
            f"BenfordRich bundle={response['release_id']} "
            f"schema={response['feature_schema_version']} "
            f"width={response['feature_width']}"
        )
        safe_print(f"BenfordRich Prob (Forged): {response['forged_score']:.6f}")
        safe_print(
            f"BenfordRich Result: {response['label']} "
            f"({response['confidence']:.2f}%)"
        )
        return {
            "score_forged": float(response["forged_score"]),
            "label": response["label"],
            "confidence": float(response["confidence"]),
            "source": "benford_rich",
            "release_id": response["release_id"],
            "feature_schema_version": response["feature_schema_version"],
            "feature_width": int(response["feature_width"]),
        }

    def _run_primary_detector(self, fname, source_type="image"):
        if PRIMARY_DETECTOR_MODE == "cnn_only":
            safe_print("=== RUNNING CNN-ONLY PRIMARY DETECTOR ===")
            return self._run_cnn_only_detector(fname)

        if PRIMARY_DETECTOR_MODE == "legacy_current":
            safe_print("=== RUNNING LEGACY CURRENT PRIMARY DETECTOR ===")
            return self._run_legacy_current_detector(fname)

        try:
            safe_print("=== RUNNING BENFORDRICH PRIMARY DETECTOR ===")
            return self._run_benford_rich_detector(fname, source_type=source_type)
        except Exception as e:
            safe_print(
                f"BenfordRich detector unavailable: {e}. "
                "Falling back to CNN-only detector."
            )
            fallback = self._run_cnn_only_detector(fname)
            fallback["source"] = f"fallback_{fallback['source']}"
            return fallback

    def _run_current_detector(self, fname, source_type="image"):
        return self._run_primary_detector(fname, source_type=source_type)

    def _run_cnn_only_detector(self, fname):
        runtime_manifest = self._get_preferred_artifact_manifest()
        try:
            p_authentic, p_forged = self._run_cnn_inference(fname, runtime_manifest)
        except Exception as e:
            safe_print(
                f"Preferred CNN bundle failed for CNN-only path: "
                f"{runtime_manifest['release_id']} ({e}). Trying legacy runtime."
            )
            runtime_manifest = self._get_legacy_artifact_manifest()
            p_authentic, p_forged = self._run_cnn_inference(fname, runtime_manifest)

        prediction = "Forged" if p_authentic <= 0.5 else "Authentic"
        confidence = (1.0 - p_authentic) if prediction == "Forged" else p_authentic
        return {
            "score_forged": float(p_forged),
            "label": prediction,
            "confidence": round(confidence * 100.0, 2),
            "source": "cnn_only",
            "release_id": runtime_manifest["release_id"],
        }

    def _prepare_pickle_compat(self):
        """
        Alias numpy internals used by pickles produced in newer Colab runtimes.
        This keeps legacy webapp environments from failing on numpy._core imports.
        """
        try:
            import sys

            sys.modules.setdefault("numpy._core", np.core)
            sys.modules.setdefault("numpy._core.multiarray", np.core.multiarray)
        except Exception as e:
            safe_print(f"Warning: numpy pickle compatibility shim failed: {e}")

    def _normalize_keras_config_value(self, value):
        if isinstance(value, dict):
            if value.get("class_name") == "DTypePolicy":
                return value.get("config", {}).get("name", "float32")

            normalized = {
                key: self._normalize_keras_config_value(sub_value)
                for key, sub_value in value.items()
            }
            if normalized.get("class_name") == "InputLayer":
                config = normalized.get("config", {})
                if (
                    isinstance(config, dict)
                    and "batch_shape" in config
                    and "batch_input_shape" not in config
                ):
                    config["batch_input_shape"] = config.pop("batch_shape")
            return normalized

        if isinstance(value, list):
            return [self._normalize_keras_config_value(item) for item in value]

        return value

    def _ensure_compatible_cnn_model(self, model_path):
        model_dir = os.path.dirname(model_path)
        model_name = os.path.basename(model_path)
        compat_model_name = f"runtime_compat_{model_name}"
        compat_model_path = os.path.join(model_dir, compat_model_name)
        if os.path.exists(compat_model_path):
            return compat_model_path

        temp_path = os.path.join(tempfile.gettempdir(), compat_model_name)
        shutil.copy2(model_path, temp_path)
        with h5py.File(temp_path, "r+") as h5_file:
            model_config = h5_file.attrs.get("model_config")
            if model_config is None:
                raise ValueError(f"model_config missing in H5 file: {model_path}")

            model_config_text = (
                model_config.decode("utf-8")
                if isinstance(model_config, bytes)
                else model_config
            )
            normalized_config = self._normalize_keras_config_value(
                json.loads(model_config_text)
            )
            h5_file.attrs.modify(
                "model_config",
                json.dumps(normalized_config).encode("utf-8"),
            )

        shutil.copy2(temp_path, compat_model_path)
        return compat_model_path

    def _load_hybrid_components(self, manifest):
        svm_path = manifest["svm_model_path"]
        scaler_path = manifest["scaler_path"]
        metadata_path = manifest["metadata_path"]

        if not (svm_path and os.path.exists(svm_path)):
            raise FileNotFoundError(f"Hybrid SVM missing: {svm_path}")
        if not (scaler_path and os.path.exists(scaler_path)):
            raise FileNotFoundError(f"Hybrid scaler missing: {scaler_path}")
        if not (metadata_path and os.path.exists(metadata_path)):
            raise FileNotFoundError(f"Hybrid metadata missing: {metadata_path}")

        self._prepare_pickle_compat()
        svm = joblib.load(svm_path)
        scaler = joblib.load(scaler_path)

        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        self._validate_hybrid_metadata(metadata, scaler)
        safe_print(
            f"Hybrid bundle={manifest['release_id']} "
            f"schema={metadata['feature_schema_version']}"
        )
        return svm, scaler, metadata

    def _validate_hybrid_metadata(self, metadata, scaler):
        expected = get_feature_contract()
        compatible_versions = set(get_compatible_feature_schema_versions())

        required_keys = [
            "feature_schema_version",
            "label_mapping",
            "cnn_score_semantics",
            "hybrid_feature_order",
            "benford_chi_scale",
            "benford_feature_order",
        ]
        missing = [k for k in required_keys if k not in metadata]
        if missing:
            raise ValueError(f"Hybrid metadata missing keys: {missing}")

        if metadata["feature_schema_version"] not in compatible_versions:
            raise ValueError(
                "feature_schema_version mismatch: "
                f"got={metadata['feature_schema_version']} "
                f"expected_one_of={sorted(compatible_versions)}"
            )

        if metadata["label_mapping"] != expected["label_mapping"]:
            raise ValueError(
                f"label_mapping mismatch: got={metadata['label_mapping']} expected={expected['label_mapping']}"
            )

        if metadata["cnn_score_semantics"] != expected["cnn_score_semantics"]:
            raise ValueError(
                f"cnn_score_semantics mismatch: got={metadata['cnn_score_semantics']} expected={expected['cnn_score_semantics']}"
            )

        if metadata["hybrid_feature_order"] != expected["hybrid_feature_order"]:
            raise ValueError("hybrid_feature_order mismatch")

        if metadata["benford_chi_scale"] != expected["benford_chi_scale"]:
            raise ValueError(
                f"benford_chi_scale mismatch: got={metadata['benford_chi_scale']} expected={expected['benford_chi_scale']}"
            )

        if metadata["benford_feature_order"] != expected["benford_feature_order"]:
            raise ValueError("benford_feature_order mismatch")

        expected_feature_count = len(expected["hybrid_feature_order"])
        scaler_feature_count = getattr(scaler, "n_features_in_", None)
        if scaler_feature_count != expected_feature_count:
            raise ValueError(
                f"scaler feature count mismatch: got={scaler_feature_count} expected={expected_feature_count}"
            )

        train_environment = metadata.get("train_environment", {})
        runtime_versions = {
            "numpy": np.__version__,
            "scikit_learn": getattr(sklearn, "__version__", None),
            "joblib": getattr(joblib, "__version__", None),
        }
        mismatches = []
        for key, runtime_value in runtime_versions.items():
            train_value = train_environment.get(key)
            if train_value and runtime_value and train_value != runtime_value:
                mismatches.append(f"{key}: train={train_value}, runtime={runtime_value}")
        if mismatches:
            safe_print(
                "Warning: hybrid artifact environment mismatch detected: "
                + "; ".join(mismatches)
            )

    def predict_result_structured(self, fname, source_type="image", require_hidden=True):
        safe_print("=== PREDICTING RESULT ===")
        safe_print(f"Primary detector mode: {PRIMARY_DETECTOR_MODE}")
        current_result = self._run_primary_detector(fname, source_type=source_type)
        request_id = create_request_id()
        strict_timeout = float(os.environ.get("T07_HIDDEN_DETECTOR_TIMEOUT_STRICT", "180"))
        optional_timeout = float(os.environ.get("T07_HIDDEN_DETECTOR_TIMEOUT_OPTIONAL", "30"))
        hidden_timeout = strict_timeout if require_hidden else optional_timeout

        try:
            hidden_result = predict_hidden_detector(
                fname,
                source_type=source_type,
                request_id=request_id,
                timeout=hidden_timeout,
            )
            fused = fuse_detector_votes(
                current_result["score_forged"],
                current_result["source"],
                hidden_result["forged_score"],
                hidden_result["label"],
                hidden_mask_path=hidden_result.get("mask_path"),
                hidden_model_name=hidden_result.get("model_name"),
                hidden_latency_ms=hidden_result.get("latency_ms"),
            )
            fused["request_id"] = request_id
            fused["current_release_id"] = current_result["release_id"]
            safe_print(
                f"Final fused result: {fused['final_label']} "
                f"(score={fused['final_score_forged']:.6f}, confidence={fused['final_confidence']:.2f}%)"
            )
            return fused
        except Exception as hidden_e:
            safe_print(f"Hidden detector unavailable: {hidden_e}")
            if require_hidden:
                raise
            fallback = build_current_only_result(
                current_result["score_forged"],
                current_result["source"],
            )
            fallback["request_id"] = request_id
            fallback["current_release_id"] = current_result["release_id"]
            fallback["hidden_error"] = str(hidden_e)
            return fallback

    def predict_benford_rich_structured(self, fname, source_type="image"):
        return self._run_benford_rich_detector(fname, source_type=source_type)

    def predict_legacy_current_structured(self, fname):
        return self._run_legacy_current_detector(fname)

    def predict_cnn_only_structured(self, fname):
        return self._run_cnn_only_detector(fname)

    def predict_result(self, fname):
        structured = self.predict_result_structured(
            fname,
            source_type="image",
            require_hidden=False,
        )
        return (
            structured["final_label"],
            f"{structured['final_confidence']:0.2f}",
        )

    def genMask(self, file_path):
        segmenter = initSegmenter()
        if os.path.exists(DEFAULT_SEGMENTER_WEIGHTS):
            segmenter.load_weights(DEFAULT_SEGMENTER_WEIGHTS)
        else:
            safe_print("Segmenter weights not found.")
            return None

        testimg = self.convert_to_ela_image(file_path, 90).resize((256, 256))
        testimg = testimg.getchannel("B")
        test = np.array(testimg) / np.max(testimg)
        test = test.reshape(-1, 256, 256, 1)
        mask = segmenter.predict(test)
        mask = mask.reshape(256, 256)
        mask = (mask * 255).astype("uint8")
        mask_im = Image.fromarray(mask)
        mask_im.save(resaved_filename, "JPEG")
        return mask_im

    def convert_to_ela_image(self, path, quality):
        try:
            import urllib.parse

            decoded_path = urllib.parse.unquote(path)
            decoded_path = os.path.abspath(decoded_path)
            safe_print("-----------path--------------", decoded_path)
            original_image = Image.open(decoded_path).convert("RGB")

            resaved_file_name = resaved_filename
            original_image.save(resaved_file_name, "JPEG", quality=quality)
            resaved_image = Image.open(resaved_file_name)

            ela_image = ImageChops.difference(original_image, resaved_image)

            extrema = ela_image.getextrema()
            max_difference = max([pix[1] for pix in extrema])
            if max_difference == 0:
                max_difference = 1
            scale = 255.0 / max_difference

            ela_image = ImageEnhance.Brightness(ela_image).enhance(scale)
            return ela_image
        except Exception as e:
            safe_print(f"ELA Error: {e}")
            return Image.new("RGB", (128, 128))

    def show_ela(self, file_path, sl=50):
        ela_im = self.convert_to_ela_image(file_path, 90)
        ela_im.save(resaved_filename, "JPEG")
        return ela_im

    def detect_edges(self, path):
        import urllib.parse

        decoded_path = urllib.parse.unquote(path)
        image = Image.open(decoded_path)
        image = image.convert("L")
        image = image.filter(ImageFilter.FIND_EDGES)
        image = np.array(image.resize((256, 256)))
        edge_im = Image.fromarray(image)
        edge_im.save(resaved_filename, "JPEG")
        return edge_im

    def luminance_gradient(self, path):
        import urllib.parse

        decoded_path = urllib.parse.unquote(path)
        decoded_path = os.path.abspath(decoded_path)
        resaved_filename_png = os.path.join(os.getcwd(), "media", "luminance_gradient.png")
        img = cv.imread(decoded_path, 0)
        if img is None:
            return Image.new("L", (600, 600))
        sobelx = cv.Sobel(img, cv.CV_64F, 1, 0, ksize=15)
        sobelx_norm = np.uint8(np.absolute(sobelx))
        image = Image.fromarray(sobelx_norm).resize((600, 600))
        image.save(resaved_filename_png, "PNG")
        return image

    def noise_analysis(self, path, quality, intensity):
        import urllib.parse

        filename = urllib.parse.unquote(path)
        filename = os.path.abspath(filename)
        resaved_filename_local = "tempresaved.jpg"
        im = Image.open(filename).convert("L")
        im.save(resaved_filename_local, "JPEG", quality=quality)
        resaved_im = Image.open(resaved_filename_local)
        na_im = ImageChops.difference(im, resaved_im)
        extrema = na_im.getextrema()
        max_diff = max([ex for ex in extrema])
        if max_diff == 0:
            max_diff = 1
        na_im = ImageEnhance.Brightness(na_im).enhance(intensity)
        return na_im

    def apply_na(self, file_path, sl=50):
        intensity = sl
        na = self.noise_analysis(file_path, 90, intensity)
        na.save(resaved_filename, "JPEG")
        return na


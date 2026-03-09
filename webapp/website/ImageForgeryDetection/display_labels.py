from __future__ import annotations

import os


DEFAULT_PRIMARY_DISPLAY_NAME = "CNN + SVM Benford"


def get_primary_detector_display_name(environ=None) -> str:
    env = environ if environ is not None else os.environ
    value = str(env.get("T07_PRIMARY_DISPLAY_NAME", DEFAULT_PRIMARY_DISPLAY_NAME)).strip()
    return value or DEFAULT_PRIMARY_DISPLAY_NAME

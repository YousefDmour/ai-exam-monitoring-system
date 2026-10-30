"""Validated, atomic persistence for local application defaults."""
import json
import math
import os
import tempfile
from copy import deepcopy
from pathlib import Path

from examwatch.exam_rules import DEFAULT_FORBIDDEN, validate_forbidden, clip_window

DEFAULT_PREFERENCES = {
    'fullscreen': True, 'camera': 0, 'minimum_duration': 1.0, 'absence_duration': 3.0,
    'confidence': .4, 'save_clips': True, 'clip_duration_seconds': 10.0,
    'forbidden_objects': list(DEFAULT_FORBIDDEN),
}


def validate_preferences(values):
    if not isinstance(values, dict):
        raise ValueError('Settings must be an object.')
    data = {**deepcopy(DEFAULT_PREFERENCES), **values}
    for key in ('fullscreen', 'save_clips'):
        if not isinstance(data[key], bool):
            raise ValueError(f'{key} must be enabled or disabled.')
    camera = float(data['camera'])
    if not math.isfinite(camera) or not camera.is_integer() or not 0 <= camera <= 10:
        raise ValueError('Camera index must be an integer from 0 to 10.')
    data['camera'] = int(camera)
    for key, low, high in (('minimum_duration', .1, 30), ('absence_duration', .1, 60), ('confidence', .05, 1)):
        data[key] = float(data[key])
        if not math.isfinite(data[key]) or not low <= data[key] <= high:
            raise ValueError(f'{key.replace("_", " ").title()} must be between {low} and {high}.')
    pre, post = clip_window(data['clip_duration_seconds'])
    data['clip_duration_seconds'] = pre + post
    data['forbidden_objects'] = validate_forbidden(data['forbidden_objects'])
    return {key: data[key] for key in DEFAULT_PREFERENCES}


def load_preferences(root):
    path = Path(root) / 'outputs/preferences.json'
    if not path.exists():
        return deepcopy(DEFAULT_PREFERENCES), ''
    try:
        saved = json.loads(path.read_text(encoding='utf-8'))
        if saved.get('version') != 1:
            raise ValueError('Unsupported settings format.')
        return validate_preferences(saved['defaults']), ''
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return deepcopy(DEFAULT_PREFERENCES), 'Saved settings could not be read. Defaults are in use; the saved file has not been changed.'


def save_preferences(root, values):
    data = validate_preferences(values)
    directory = Path(root) / 'outputs'
    directory.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=directory,
                                         prefix='.preferences-', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            json.dump({'version': 1, 'defaults': data}, stream, indent=2)
            stream.write('\n')
        os.replace(str(temporary), str(directory / 'preferences.json'))
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return data

"""Supported object choices and session clip settings."""
import math

# These names match standard YOLO COCO labels. The loaded model's names are
# checked before opening the camera; adding a text label cannot train a detector.
SUPPORTED_OBJECTS = ('CELL PHONE', 'BOOK', 'CLOCK', 'LAPTOP', 'REMOTE', 'MOUSE',
                     'KEYBOARD', 'BACKPACK', 'HANDBAG', 'BOTTLE', 'CUP', 'SCISSORS')
DEFAULT_FORBIDDEN = ('CELL PHONE', 'BOOK')


def validate_forbidden(names):
    if not isinstance(names, (list, tuple, set)) or any(name not in SUPPORTED_OBJECTS for name in names):
        raise ValueError('Choose forbidden objects from the supported detection list.')
    return sorted(set(names))


def model_object_classes(names, forbidden):
    forbidden = validate_forbidden(forbidden)
    items = names.items() if isinstance(names, dict) else enumerate(names)
    classes = {int(index): name.upper() for index, name in items if name.upper() in forbidden}
    missing = set(forbidden) - set(classes.values())
    if missing:
        raise ValueError('The loaded model does not support: ' + ', '.join(sorted(missing)))
    return classes


def clip_window(duration):
    duration = float(duration)
    if not math.isfinite(duration) or not 5 <= duration <= 15:
        raise ValueError('Clip duration must be between 5 and 15 seconds (total).')
    return duration / 2, duration / 2

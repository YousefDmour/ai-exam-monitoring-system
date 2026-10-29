"""Heuristic setup guidance; these are not cheating signals."""


def assess_quality(frame, landmarks, cv2):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    brightness = float(gray.mean())
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    warnings = []
    if brightness < 55:
        warnings.append('Increase lighting')
    elif brightness > 225:
        warnings.append('Reduce bright light / backlighting')
    if sharpness < 45:
        warnings.append('Image is blurry; steady or focus the camera')
    if len(landmarks) == 1:
        face = landmarks[0]
        xs, ys = [point.x for point in face], [point.y for point in face]
        width = max(xs) - min(xs)
        if width < .15:
            warnings.append('Move closer to the camera')
        if width > .8 or min(xs) < .01 or max(xs) > .99 or min(ys) < .01 or max(ys) > .99:
            warnings.append('Move back and keep your full face visible')
    elif not landmarks:
        warnings.append('Keep one face visible for calibration')
    else:
        warnings.append('Only one person should be visible during calibration')
    return {'brightness': round(brightness, 1), 'sharpness': round(sharpness, 1),
            'warnings': warnings, 'calibration_ready': not warnings and len(landmarks) == 1}

#!/usr/bin/env python
"""Generate a test image with a pothole-like object"""
import cv2
import numpy as np
from pathlib import Path

# Create a test image
img = np.ones((480, 640, 3), dtype=np.uint8) * 150  # Gray background

# Draw a circle that looks like a pothole
cv2.circle(img, (320, 240), 60, (50, 50, 50), -1)  # Dark circle in center
cv2.circle(img, (320, 240), 55, (30, 30, 30), -1)  # Darker inner circle

# Add some noise/texture
for _ in range(100):
    x, y = np.random.randint(260, 380), np.random.randint(180, 300)
    cv2.circle(img, (x, y), 2, (40, 40, 40), -1)

# Save it
output_path = Path(__file__).parent / "test_pothole.jpg"
cv2.imwrite(str(output_path), img)
print(f"Test image created: {output_path}")
print(f"  Size: {img.shape}")

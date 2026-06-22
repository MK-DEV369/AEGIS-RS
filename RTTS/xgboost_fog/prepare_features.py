from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np
import pandas as pd

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp", ".webp")


def _find_image_by_stem(images_dir: Path, stem: str) -> Path | None:
    for ext in IMAGE_EXTENSIONS:
        candidate = images_dir / f"{stem}{ext}"
        if candidate.exists():
            return candidate
    return None


def _dark_channel(bgr: np.ndarray, kernel_size: int = 15) -> np.ndarray:
    minimum = np.min(bgr, axis=2)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))
    return cv2.erode(minimum, kernel)


def _clear_like_transform(image: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l_enhanced = clahe.apply(l_channel)

    lab_enhanced = cv2.merge([l_enhanced, a_channel, b_channel])
    enhanced = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)

    alpha = 1.15
    beta = 8
    enhanced = cv2.convertScaleAbs(enhanced, alpha=alpha, beta=beta)

    return enhanced


def _extract_features_from_image(image: np.ndarray) -> dict[str, float]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    grad_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    grad_mag = cv2.magnitude(grad_x, grad_y)

    saturation = hsv[:, :, 1].astype(np.float32)
    value = hsv[:, :, 2].astype(np.float32)

    dark = _dark_channel(image)
    color_attenuation = value - saturation

    p05 = float(np.percentile(gray, 5))
    p95 = float(np.percentile(gray, 95))

    return {
        "gray_mean": float(gray.mean()),
        "gray_std": float(gray.std()),
        "gray_p10": float(np.percentile(gray, 10)),
        "gray_p90": float(np.percentile(gray, 90)),
        "contrast_p95_p05": p95 - p05,
        "laplacian_var": lap_var,
        "gradient_mean": float(grad_mag.mean()),
        "gradient_std": float(grad_mag.std()),
        "saturation_mean": float(saturation.mean()),
        "saturation_std": float(saturation.std()),
        "value_mean": float(value.mean()),
        "value_std": float(value.std()),
        "dark_channel_mean": float(dark.mean()),
        "dark_channel_std": float(dark.std()),
        "dark_channel_p10": float(np.percentile(dark, 10)),
        "dark_channel_p90": float(np.percentile(dark, 90)),
        "color_attenuation_mean": float(color_attenuation.mean()),
        "color_attenuation_std": float(color_attenuation.std()),
        "color_attenuation_p10": float(np.percentile(color_attenuation, 10)),
        "color_attenuation_p90": float(np.percentile(color_attenuation, 90)),
    }


def extract_fog_features(
    image_array: np.ndarray | None = None,
    image_path: Path | str | None = None,
    image_size: int = 256
) -> dict[str, float] | None:
    """
    Extract fog features from either an in-memory numpy array or a file path.
    """
    if image_array is not None:
        image = image_array
    elif image_path is not None:
        image = cv2.imread(str(image_path))
    else:
        raise ValueError("Must provide either image_array or image_path")

    if image is None:
        return None

    # Only resize if the dimensions don't already match to save CPU during real-time inference
    if image.shape[0] != image_size or image.shape[1] != image_size:
        image = cv2.resize(image, (image_size, image_size), interpolation=cv2.INTER_AREA)
        
    return _extract_features_from_image(image)


def _iter_image_paths(directory: Path) -> Iterable[Path]:
    for path in directory.rglob("*"):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            yield path


def _load_stems(list_file: Path) -> list[str]:
    lines = list_file.read_text(encoding="utf-8", errors="ignore").splitlines()
    return [line.strip() for line in lines if line.strip()]


def build_dataset(
    rtts_root: Path,
    negatives_dir: Path | None,
    positives_list: Path | None,
    image_size: int,
    auto_pseudo_negatives: bool,
    max_pseudo_negatives: int,
) -> pd.DataFrame:
    positives_images_dir = rtts_root / "JPEGImages"

    positive_records: list[dict[str, float | int | str]] = []
    if positives_list and positives_list.exists():
        stems = _load_stems(positives_list)
        positive_paths = [
            image_path
            for stem in stems
            if (image_path := _find_image_by_stem(positives_images_dir, stem)) is not None
        ]
    else:
        positive_paths = list(_iter_image_paths(positives_images_dir))

    for path in positive_paths:
        features = extract_fog_features(image_path=path, image_size=image_size)
        if features is None:
            continue
        row = {**features, "label": 1, "image_path": str(path)}
        positive_records.append(row)

    negative_records: list[dict[str, float | int | str]] = []
    if negatives_dir is not None:
        for path in _iter_image_paths(negatives_dir):
            features = extract_fog_features(image_path=path, image_size=image_size)
            if features is None:
                continue
            row = {**features, "label": 0, "image_path": str(path)}
            negative_records.append(row)
    elif auto_pseudo_negatives:
        count = 0
        for path in positive_paths:
            image = cv2.imread(str(path))
            if image is None:
                continue
            image = cv2.resize(image, (image_size, image_size), interpolation=cv2.INTER_AREA)
            clear_like = _clear_like_transform(image)
            features = _extract_features_from_image(clear_like)
            row = {**features, "label": 0, "image_path": f"pseudo_clear::{path}"}
            negative_records.append(row)
            count += 1
            if max_pseudo_negatives > 0 and count >= max_pseudo_negatives:
                break

    records = positive_records + negative_records
    if not records:
        raise RuntimeError("No samples were extracted. Check your dataset paths.")

    return pd.DataFrame(records)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create tabular fog features for XGBoost training.")
    parser.add_argument(
        "--rtts-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Path to RTTS root folder (contains JPEGImages/ImageSets).",
    )
    parser.add_argument(
        "--positives-list",
        type=Path,
        default=None,
        help="Optional image-stem list file (e.g., RTTS/ImageSets/Main/test.txt).",
    )
    parser.add_argument(
        "--negatives-dir",
        type=Path,
        default=None,
        help="Folder with non-fog images used as negative class.",
    )
    parser.add_argument("--image-size", type=int, default=256, help="Resize side-length before extraction.")
    parser.add_argument(
        "--auto-pseudo-negatives",
        action="store_true",
        help="Generate pseudo non-fog negatives from fog images (bootstrap mode).",
    )
    parser.add_argument(
        "--max-pseudo-negatives",
        type=int,
        default=0,
        help="Limit pseudo negatives count; 0 means use all positives.",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("data") / "fog_features.csv",
        help="Output CSV path.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    default_list = args.rtts_root / "ImageSets" / "Main" / "test.txt"
    positives_list = args.positives_list if args.positives_list is not None else default_list

    data = build_dataset(
        rtts_root=args.rtts_root,
        negatives_dir=args.negatives_dir,
        positives_list=positives_list,
        image_size=args.image_size,
        auto_pseudo_negatives=args.auto_pseudo_negatives,
        max_pseudo_negatives=args.max_pseudo_negatives,
    )

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(args.output_csv, index=False)

    label_counts = data["label"].value_counts().to_dict()
    print(f"Saved features to: {args.output_csv}")
    print(f"Samples: {len(data)} | Label counts: {label_counts}")

    if 0 not in label_counts:
        print("Warning: no negative samples found. Add --negatives-dir or --auto-pseudo-negatives.")


if __name__ == "__main__":
    main()
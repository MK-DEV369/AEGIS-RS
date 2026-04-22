from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

import matplotlib.pyplot as plt
import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Visualize YOLO training results.csv and optionally compare two runs."
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path("results.csv"),
        help="Primary YOLO results CSV (default: results.csv)",
    )
    parser.add_argument(
        "--compare-csv",
        type=Path,
        default=None,
        help="Optional second YOLO results CSV for comparison",
    )
    parser.add_argument(
        "--label",
        type=str,
        default="run_a",
        help="Legend label for primary run",
    )
    parser.add_argument(
        "--compare-label",
        type=str,
        default="run_b",
        help="Legend label for comparison run",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("plots"),
        help="Directory to save output plots and summary",
    )
    return parser.parse_args()


def load_results(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {path}")

    df = pd.read_csv(path)
    df.columns = [c.strip() for c in df.columns]

    if "epoch" not in df.columns:
        raise ValueError(f"CSV must contain an 'epoch' column: {path}")

    return df


def maybe_plot(
    ax,
    df_a: pd.DataFrame,
    col: str,
    label_a: str,
    df_b: pd.DataFrame | None = None,
    label_b: str | None = None,
) -> None:
    if col not in df_a.columns and (df_b is None or col not in df_b.columns):
        ax.set_visible(False)
        return

    if col in df_a.columns:
        ax.plot(df_a["epoch"], df_a[col], marker="o", linewidth=1.8, label=label_a)

    if df_b is not None and col in df_b.columns:
        ax.plot(df_b["epoch"], df_b[col], marker="o", linewidth=1.8, linestyle="--", label=label_b)

    ax.set_title(col)
    ax.set_xlabel("Epoch")
    ax.grid(True, alpha=0.3)
    ax.legend()


def best_epoch(df: pd.DataFrame, metric_col: str, mode: str) -> Dict[str, float] | Dict[str, str]:
    if metric_col not in df.columns:
        return {"status": f"missing:{metric_col}"}

    if mode == "max":
        idx = df[metric_col].idxmax()
    else:
        idx = df[metric_col].idxmin()

    row = df.loc[idx]
    return {
        "epoch": int(row["epoch"]),
        "value": float(row[metric_col]),
    }


def build_summary(df: pd.DataFrame, name: str) -> Dict[str, object]:
    summary: Dict[str, object] = {
        "name": name,
        "epochs": int(df["epoch"].max()),
        "best_mAP50_95": best_epoch(df, "metrics/mAP50-95(B)", mode="max"),
        "best_mAP50": best_epoch(df, "metrics/mAP50(B)", mode="max"),
        "best_precision": best_epoch(df, "metrics/precision(B)", mode="max"),
        "best_recall": best_epoch(df, "metrics/recall(B)", mode="max"),
        "lowest_val_box_loss": best_epoch(df, "val/box_loss", mode="min"),
        "lowest_val_cls_loss": best_epoch(df, "val/cls_loss", mode="min"),
        "lowest_val_dfl_loss": best_epoch(df, "val/dfl_loss", mode="min"),
    }

    if "time" in df.columns:
        summary["final_time_seconds"] = float(df["time"].iloc[-1])
        summary["avg_time_per_epoch_seconds"] = float(df["time"].diff().dropna().mean()) if len(df) > 1 else 0.0

    return summary


def save_detection_metrics_plot(
    out_dir: Path,
    df_a: pd.DataFrame,
    label_a: str,
    df_b: pd.DataFrame | None,
    label_b: str,
) -> Path:
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("YOLO Detection Metrics vs Epoch", fontsize=16)

    metric_cols = [
        "metrics/precision(B)",
        "metrics/recall(B)",
        "metrics/mAP50(B)",
        "metrics/mAP50-95(B)",
    ]

    for ax, col in zip(axes.flatten(), metric_cols):
        maybe_plot(ax, df_a, col, label_a, df_b, label_b)

    fig.tight_layout(rect=[0, 0, 1, 0.96])
    out_path = out_dir / "01_detection_metrics.png"
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def save_losses_plot(
    out_dir: Path,
    df_a: pd.DataFrame,
    label_a: str,
    df_b: pd.DataFrame | None,
    label_b: str,
) -> Path:
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    fig.suptitle("YOLO Loss Curves vs Epoch", fontsize=16)

    loss_cols = [
        "train/box_loss",
        "train/cls_loss",
        "train/dfl_loss",
        "val/box_loss",
        "val/cls_loss",
        "val/dfl_loss",
    ]

    for ax, col in zip(axes.flatten(), loss_cols):
        maybe_plot(ax, df_a, col, label_a, df_b, label_b)

    fig.tight_layout(rect=[0, 0, 1, 0.96])
    out_path = out_dir / "02_losses.png"
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def save_lr_plot(
    out_dir: Path,
    df_a: pd.DataFrame,
    label_a: str,
    df_b: pd.DataFrame | None,
    label_b: str,
) -> Path:
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    fig.suptitle("Learning Rate Schedules", fontsize=16)

    lr_cols = ["lr/pg0", "lr/pg1", "lr/pg2"]

    for ax, col in zip(axes.flatten(), lr_cols):
        maybe_plot(ax, df_a, col, label_a, df_b, label_b)

    fig.tight_layout(rect=[0, 0, 1, 0.92])
    out_path = out_dir / "03_learning_rates.png"
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def save_time_plot(
    out_dir: Path,
    df_a: pd.DataFrame,
    label_a: str,
    df_b: pd.DataFrame | None,
    label_b: str,
) -> Path | None:
    if "time" not in df_a.columns and (df_b is None or "time" not in df_b.columns):
        return None

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle("Training Time Analysis", fontsize=16)

    maybe_plot(axes[0], df_a, "time", f"{label_a} cumulative", df_b, f"{label_b} cumulative")
    axes[0].set_ylabel("Seconds")

    if "time" in df_a.columns:
        per_epoch_a = df_a["time"].diff().fillna(df_a["time"]).clip(lower=0)
        axes[1].plot(df_a["epoch"], per_epoch_a, marker="o", linewidth=1.8, label=f"{label_a} per-epoch")

    if df_b is not None and "time" in df_b.columns:
        per_epoch_b = df_b["time"].diff().fillna(df_b["time"]).clip(lower=0)
        axes[1].plot(df_b["epoch"], per_epoch_b, marker="o", linewidth=1.8, linestyle="--", label=f"{label_b} per-epoch")

    axes[1].set_title("time_per_epoch")
    axes[1].set_xlabel("Epoch")
    axes[1].set_ylabel("Seconds")
    axes[1].grid(True, alpha=0.3)
    axes[1].legend()

    fig.tight_layout(rect=[0, 0, 1, 0.92])
    out_path = out_dir / "04_time_analysis.png"
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def main() -> None:
    args = parse_args()

    df_a = load_results(args.csv)
    df_b = load_results(args.compare_csv) if args.compare_csv else None

    args.output_dir.mkdir(parents=True, exist_ok=True)

    generated: List[str] = []
    generated.append(str(save_detection_metrics_plot(args.output_dir, df_a, args.label, df_b, args.compare_label)))
    generated.append(str(save_losses_plot(args.output_dir, df_a, args.label, df_b, args.compare_label)))
    generated.append(str(save_lr_plot(args.output_dir, df_a, args.label, df_b, args.compare_label)))

    time_plot = save_time_plot(args.output_dir, df_a, args.label, df_b, args.compare_label)
    if time_plot is not None:
        generated.append(str(time_plot))

    summary = {
        args.label: build_summary(df_a, args.label),
    }

    if df_b is not None:
        summary[args.compare_label] = build_summary(df_b, args.compare_label)

    summary_path = args.output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("Saved plots:")
    for p in generated:
        print("-", p)
    print("Saved summary:", summary_path)


if __name__ == "__main__":
    main()

"""Render PNG images from the L_xyz.npy files stored beside this script.

This script performs no ray tracing. By default it reads numerical results
from this directory and writes images to the ``png`` subdirectory.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


HERE = Path(__file__).resolve().parent
DEFAULT_INPUT = HERE / "beijing_temple"
DEFAULT_OUTPUT = HERE / "png"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--start-frame", type=int, default=0)
    parser.add_argument("--stop-frame", type=int, default=None)
    parser.add_argument("--png-every", type=int, default=1)
    parser.add_argument("--vmin", type=float, default=50.0)
    parser.add_argument("--vmax", type=float, default=150.0)
    parser.add_argument("--dpi", type=int, default=130)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def save_figure(fig: plt.Figure, path: Path, dpi: int, **kwargs) -> None:
    temporary = path.with_name(path.name + ".tmp")
    fig.savefig(temporary, format="png", dpi=dpi, **kwargs)
    os.replace(temporary, path)


def render_layers(
    stack: np.ndarray,
    frame_output: Path,
    zs: np.ndarray,
    time_s: float,
    tx_z: float,
    cell_size: float,
    args: argparse.Namespace,
) -> int:
    rendered = 0
    for layer_index in range(0, len(zs), args.png_every):
        z = float(zs[layer_index])
        path = frame_output / f"L_z{z:05.1f}.png"
        if path.is_file() and not args.overwrite:
            continue
        fig, ax = plt.subplots(figsize=(5.2, 4.6))
        image = ax.imshow(
            stack[layer_index],
            origin="lower",
            cmap="jet",
            vmin=args.vmin,
            vmax=args.vmax,
        )
        ax.set_title(
            f"Path Loss (dB), t={time_s:.1f} s, RX z={z:.0f} m, "
            f"TX z={tx_z:.1f} m"
        )
        ax.set_xlabel(f"x cell ({cell_size:g} m)")
        ax.set_ylabel(f"y cell ({cell_size:g} m)")
        fig.colorbar(image, ax=ax, label="Path Loss (dB)")
        fig.tight_layout()
        save_figure(fig, path, args.dpi)
        plt.close(fig)
        rendered += 1
    return rendered


def render_preview(
    stack: np.ndarray,
    frame_output: Path,
    zs: np.ndarray,
    time_s: float,
    args: argparse.Namespace,
) -> int:
    path = frame_output / "preview_every_10m.png"
    if path.is_file() and not args.overwrite:
        return 0
    indices = [
        index
        for index, z in enumerate(zs)
        if abs(float(z) % 10.0) < 1e-6
    ]
    if not indices:
        return 0

    columns = 6
    rows = int(math.ceil(len(indices) / columns))
    fig, axes = plt.subplots(
        rows,
        columns,
        figsize=(3.0 * columns, 2.8 * rows),
        squeeze=False,
    )
    image = None
    for plot_index, ax in enumerate(axes.ravel()):
        if plot_index >= len(indices):
            ax.axis("off")
            continue
        layer_index = indices[plot_index]
        z = float(zs[layer_index])
        image = ax.imshow(
            stack[layer_index],
            origin="lower",
            cmap="jet",
            vmin=args.vmin,
            vmax=args.vmax,
        )
        ax.set_title(f"RX z={z:.0f} m")
        ax.set_xticks([])
        ax.set_yticks([])
    if image is not None:
        fig.colorbar(image, ax=axes, fraction=0.02, label="Path Loss (dB)")
    fig.suptitle(f"Dynamic GT, t={time_s:.1f} s")
    save_figure(fig, path, 140, bbox_inches="tight")
    plt.close(fig)
    return 1


def main() -> None:
    args = parse_args()
    if args.png_every <= 0 or args.dpi <= 0:
        raise ValueError("--png-every and --dpi must be positive")
    if args.vmax <= args.vmin:
        raise ValueError("--vmax must be larger than --vmin")

    input_dir = args.input.resolve()
    output_dir = args.output.resolve()
    config_path = input_dir / "run_config.json"
    z_path = input_dir / "z_m.npy"
    times_path = input_dir / "times_s.npy"
    for path in (config_path, z_path, times_path):
        if not path.is_file():
            raise FileNotFoundError(f"Required ray-tracing file not found: {path}")

    config = json.loads(config_path.read_text(encoding="utf-8"))
    zs = np.load(z_path).astype(np.float64)
    times = np.load(times_path).astype(np.float64)
    stop_frame = len(times) if args.stop_frame is None else args.stop_frame
    if not (0 <= args.start_frame < stop_frame <= len(times)):
        raise ValueError(
            f"Require 0 <= start-frame < stop-frame <= {len(times)}"
        )

    tx_z = float(config["tx_xyz_m"][2])
    cell_size = float(config["cell_size_m"][0])
    map_width, map_height = map(float, config["map_size_m"])
    expected_shape = (
        len(zs),
        int(round(map_height / cell_size)),
        int(round(map_width / cell_size)),
    )
    source_frames = input_dir / "frames"
    output_frames = output_dir / "frames"
    output_frames.mkdir(parents=True, exist_ok=True)

    selected = 0
    total_rendered = 0
    for frame_dir in sorted(source_frames.iterdir()):
        if not frame_dir.is_dir():
            continue
        metadata_path = frame_dir / "meta.json"
        stack_path = frame_dir / "L_xyz.npy"
        if not metadata_path.is_file() or not stack_path.is_file():
            continue
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        frame_index = int(metadata["frame_index"])
        if not args.start_frame <= frame_index < stop_frame:
            continue
        stack = np.load(stack_path, mmap_mode="r")
        if stack.shape != expected_shape:
            raise ValueError(
                f"{stack_path} has shape {stack.shape}; expected {expected_shape}"
            )
        frame_output = output_frames / frame_dir.name
        frame_output.mkdir(parents=True, exist_ok=True)
        rendered = render_layers(
            stack,
            frame_output,
            zs,
            float(times[frame_index]),
            tx_z,
            cell_size,
            args,
        )
        rendered += render_preview(
            stack,
            frame_output,
            zs,
            float(times[frame_index]),
            args,
        )
        selected += 1
        total_rendered += rendered
        print(
            f"[frame {frame_index:04d}] new_png_files={rendered} "
            f"-> {frame_output}",
            flush=True,
        )

    if selected == 0:
        raise RuntimeError("The requested range contains no completed frames")
    print(
        f"done: selected_frames={selected}, new_png_files={total_rendered}",
        flush=True,
    )


if __name__ == "__main__":
    main()

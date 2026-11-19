import argparse
import json
import shutil
import subprocess
import sys

from pathlib import Path


def load_config(config_path):
    with open(config_path, "r", encoding="utf-8") as file:
        return json.load(file)


def resolve_path(path, config_dir):
    path = Path(path)

    if not path.is_absolute():
        path = config_dir / path

    return path.resolve()


def run():

    parser = argparse.ArgumentParser(
        description="Crop a video using FFmpeg."
    )

    parser.add_argument(
        "--config",
        default=Path(__file__).parent / "crop-config.json"
    )

    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    config_dir = config_path.parent

    config = load_config(config_path)

    # Resolve paths

    input_path = resolve_path(config["input"], config_dir)
    output_path = resolve_path(config["output"], config_dir)

    if not input_path.is_file():
        raise FileNotFoundError(
            f"Input file not found: {input_path}"
        )

    if input_path == output_path:
        raise ValueError(
            "Input and output files must be different."
        )

    # Crop parameters

    crop = config["crop"]

    x = int(crop["x"])
    y = int(crop["y"])
    width = int(crop["width"])
    height = int(crop["height"])

    if x < 0 or y < 0:
        raise ValueError(
            "Crop coordinates cannot be negative."
        )

    if width <= 0 or height <= 0:
        raise ValueError(
            "Crop dimensions must be positive."
        )

    # Common compatibility requirement for yuv420p.

    if any(value % 2 != 0 for value in (x, y, width, height)):
        raise ValueError(
            "Crop coordinates and dimensions must be even numbers."
        )

    # FFmpeg settings

    ffmpeg = config.get("ffmpegPath", "ffmpeg")

    preset = config.get("preset", "ultrafast")
    crf = int(config.get("crf", 18))

    audio_codec = config.get("audioCodec", "copy")

    if not 0 <= crf <= 51:
        raise ValueError(
            "CRF must be between 0 and 51."
        )

    if shutil.which(ffmpeg) is None and not Path(ffmpeg).is_file():
        raise FileNotFoundError(
            f"FFmpeg executable not found: {ffmpeg}"
        )

    # Create output directory

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    # Build crop filter

    crop_filter = f"crop={width}:{height}:{x}:{y}"

    # Build FFmpeg command

    command = [
        ffmpeg,

        "-hide_banner",
        "-y",

        "-i", str(input_path),

        "-map", "0:v:0",
        "-map", "0:a?",

        "-vf", crop_filter,

        "-c:v", "libx264",
        "-preset", preset,
        "-crf", str(crf),

        "-pix_fmt", "yuv420p",

        "-c:a", audio_codec,

        str(output_path)
    ]

    # Display settings

    print(f"Input:  {input_path}")
    print(f"Output: {output_path}")

    print("\nCrop settings:")
    print(f"X:      {x}")
    print(f"Y:      {y}")
    print(f"Width:  {width}")
    print(f"Height: {height}")

    print(f"\nPreset: {preset}")
    print(f"CRF:    {crf}")

    print("\nStarting FFmpeg...\n")

    # Execute

    subprocess.run(command, check=True)

    print("\nVideo successfully cropped!")


if __name__ == "__main__":

    try:
        run()

    except Exception as error:
        print(
            f"\nERROR: {error}",
            file=sys.stderr
        )
        sys.exit(1)
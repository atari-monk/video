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

def parse_time(value):
    """Accept seconds, MM:SS or HH:MM:SS."""

    value = str(value)

    try:
        if ":" not in value:
            seconds = float(value)
        else:
            parts = value.split(":")

            if len(parts) not in (2, 3):
                raise ValueError()

            numbers = [float(part) for part in parts]

            if any(number < 0 for number in numbers):
                raise ValueError()

            if any(number >= 60 for number in numbers[1:]):
                raise ValueError()

            if len(numbers) == 2:
                seconds = numbers[0] * 60 + numbers[1]
            else:
                seconds = (
                    numbers[0] * 3600
                    + numbers[1] * 60
                    + numbers[2]
                )

    except ValueError:
        raise ValueError(f"Invalid time format: {value}")

    if seconds < 0:
        raise ValueError("Time cannot be negative.")

    return seconds

def get_duration(ffprobe, input_path):
    """Get video duration using FFprobe."""

    command = [
        ffprobe,
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(input_path)
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=True
    )

    duration = float(result.stdout.strip())

    if duration <= 0:
        raise ValueError("Invalid video duration.")

    return duration

def run():
    parser = argparse.ArgumentParser(
        description="Trim video from the beginning and/or end."
    )

    parser.add_argument(
        "--config",
        default=Path(__file__).parent / "trim-config.json"
    )

    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    config_dir = config_path.parent

    config = load_config(config_path)

    input_path = resolve_path(config["input"], config_dir)
    output_path = resolve_path(config["output"], config_dir)

    trim_start = parse_time(config.get("trimStart", "0"))
    trim_end = parse_time(config.get("trimEnd", "0"))

    mode = config.get("mode", "copy")
    ffmpeg = config.get("ffmpegPath", "ffmpeg")

    if not input_path.is_file():
        raise FileNotFoundError(
            f"Input file not found: {input_path}"
        )

    if input_path == output_path:
        raise ValueError(
            "Input and output files must be different."
        )

    if mode not in ("copy", "precise"):
        raise ValueError(
            "Mode must be 'copy' or 'precise'."
        )

    ffprobe = config.get("ffprobePath", "ffprobe")

    if shutil.which(ffmpeg) is None and not Path(ffmpeg).is_file():
        raise FileNotFoundError(
            f"FFmpeg executable not found: {ffmpeg}"
        )

    if shutil.which(ffprobe) is None and not Path(ffprobe).is_file():
        raise FileNotFoundError(
            f"FFprobe executable not found: {ffprobe}"
        )

    # Get original video duration.

    duration = get_duration(ffprobe, input_path)

    # Calculate remaining video duration.

    output_duration = duration - trim_start - trim_end

    if output_duration <= 0:
        raise ValueError(
            "Trimming would remove the entire video."
        )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    # Build FFmpeg command.

    command = [
        ffmpeg,
        "-hide_banner",
        "-y"
    ]

    if mode == "copy":
        # Fast seeking before input decoding.

        command += [
            "-ss", str(trim_start),
            "-i", str(input_path),
            "-t", str(output_duration),
            "-map", "0",
            "-c", "copy"
        ]

    else:
        # Accurate seeking after input decoding.

        command += [
            "-i", str(input_path),
            "-ss", str(trim_start),
            "-t", str(output_duration),
            "-map", "0:v?",
            "-map", "0:a?",
            "-c:v", config.get("videoCodec", "libx264"),
            "-c:a", config.get("audioCodec", "aac"),
            "-preset", config.get("videoPreset", "veryfast"),
            "-crf", str(config.get("videoCrf", 18))
        ]

    command += [
        str(arg) for arg in config.get("extraArgs", [])
    ]

    command.append(str(output_path))

    # Display operation information.

    print(f"Input:           {input_path}")
    print(f"Output:          {output_path}")
    print(f"Original length: {duration:.2f} seconds")
    print(f"Trim start:      {trim_start:.2f} seconds")
    print(f"Trim end:        {trim_end:.2f} seconds")
    print(f"Output length:   {output_duration:.2f} seconds")
    print(f"Mode:            {mode}")
    print()

    # Execute FFmpeg.

    subprocess.run(command, check=True)

    print("\nVideo successfully trimmed!")

if __name__ == "__main__":
    try:
        run()

    except Exception as error:
        print(f"\nERROR: {error}", file=sys.stderr)
        sys.exit(1)
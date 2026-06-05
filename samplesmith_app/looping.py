"""WAV loop-marker helpers for SampleSmith."""

from __future__ import annotations

from pathlib import Path

def read_wav_smpl_loop_points(path: Path) -> tuple[int, int] | None:
    """Read the first WAV smpl-loop start/end pair if present.

    Decent Sampler can use embedded WAV loop markers when explicit loopStart /
    loopEnd attributes are absent. SampleSmith keeps this small parser as a safe
    dependency-free first step toward importing those markers into the GUI.
    """
    try:
        with path.open("rb") as handle:
            if handle.read(4) != b"RIFF":
                return None
            handle.seek(8)
            if handle.read(4) != b"WAVE":
                return None
            while True:
                chunk_id = handle.read(4)
                if len(chunk_id) < 4:
                    return None
                size_bytes = handle.read(4)
                if len(size_bytes) < 4:
                    return None
                chunk_size = int.from_bytes(size_bytes, "little", signed=False)
                chunk_data_start = handle.tell()
                if chunk_id == b"smpl" and chunk_size >= 60:
                    data = handle.read(chunk_size)
                    loop_count = int.from_bytes(data[28:32], "little", signed=False)
                    if loop_count < 1 or len(data) < 60:
                        return None
                    start = int.from_bytes(data[44:48], "little", signed=False)
                    end = int.from_bytes(data[48:52], "little", signed=False)
                    return (start, end) if end > start else None
                handle.seek(chunk_data_start + chunk_size + (chunk_size % 2))
    except OSError:
        return None

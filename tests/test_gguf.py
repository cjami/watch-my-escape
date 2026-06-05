import struct
from pathlib import Path

import pytest

from watch_my_escape.llm.gguf import read_sampling_metadata


def test_read_sampling_metadata_reads_general_sampling_keys(tmp_path):
    model_path = tmp_path / "sampling.gguf"
    _write_gguf(
        model_path,
        {
            "general.sampling.temp": (6, 0.7),
            "general.sampling.top_p": (6, 0.9),
            "general.sampling.top_k": (4, 32),
        },
    )

    metadata = read_sampling_metadata(model_path)

    assert metadata.temperature == pytest.approx(0.7)
    assert metadata.top_p == pytest.approx(0.9)
    assert metadata.top_k == 32


def _write_gguf(model_path: Path, metadata: dict[str, tuple[int, float | int]]) -> None:
    with model_path.open("wb") as file:
        file.write(b"GGUF")
        file.write(struct.pack("<IQQ", 3, 0, len(metadata)))
        for key, (value_type, value) in metadata.items():
            encoded_key = key.encode("utf-8")
            file.write(struct.pack("<Q", len(encoded_key)))
            file.write(encoded_key)
            file.write(struct.pack("<I", value_type))
            if value_type == 6:
                file.write(struct.pack("<f", value))
            else:
                file.write(struct.pack("<I", value))

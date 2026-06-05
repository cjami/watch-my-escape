"""Minimal GGUF metadata reader for sampling defaults."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import IntEnum
from typing import TYPE_CHECKING, BinaryIO, cast

if TYPE_CHECKING:
    from pathlib import Path


class GgufValueType(IntEnum):
    """GGUF metadata value types."""

    UINT8 = 0
    INT8 = 1
    UINT16 = 2
    INT16 = 3
    UINT32 = 4
    INT32 = 5
    FLOAT32 = 6
    BOOL = 7
    STRING = 8
    ARRAY = 9
    UINT64 = 10
    INT64 = 11
    FLOAT64 = 12


@dataclass(frozen=True, slots=True)
class GgufSamplingMetadata:
    """Sampling recommendations embedded in GGUF metadata."""

    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None


class GgufMetadataError(ValueError):
    """Raised when GGUF metadata cannot be read."""


SCALAR_FORMATS = {
    GgufValueType.UINT8: "<B",
    GgufValueType.INT8: "<b",
    GgufValueType.UINT16: "<H",
    GgufValueType.INT16: "<h",
    GgufValueType.UINT32: "<I",
    GgufValueType.INT32: "<i",
    GgufValueType.FLOAT32: "<f",
    GgufValueType.BOOL: "<?",
    GgufValueType.UINT64: "<Q",
    GgufValueType.INT64: "<q",
    GgufValueType.FLOAT64: "<d",
}


def read_sampling_metadata(model_path: Path) -> GgufSamplingMetadata:
    """Read sampling recommendations from a GGUF model file."""
    metadata = read_metadata(model_path)
    return GgufSamplingMetadata(
        temperature=_optional_float(metadata, "general.sampling.temp", "general.sampler.temp"),
        top_p=_optional_float(metadata, "general.sampling.top_p", "general.sampler.top_p"),
        top_k=_optional_int(metadata, "general.sampling.top_k", "general.sampler.top_k"),
    )


def read_metadata(model_path: Path) -> dict[str, object]:
    """Read scalar GGUF metadata key-value pairs."""
    with model_path.open("rb") as file:
        magic = file.read(4)
        if magic != b"GGUF":
            msg = f"Not a GGUF file: {model_path}"
            raise GgufMetadataError(msg)

        _version = _read_uint32(file)
        _tensor_count = _read_uint64(file)
        metadata_count = _read_uint64(file)
        return dict(_read_key_value(file) for _ in range(metadata_count))


def _read_key_value(file: BinaryIO) -> tuple[str, object]:
    key = _read_string(file)
    value_type = GgufValueType(_read_uint32(file))
    return key, _read_value(file, value_type)


def _read_value(file: BinaryIO, value_type: GgufValueType) -> object:
    if value_type is GgufValueType.STRING:
        return _read_string(file)
    if value_type is GgufValueType.ARRAY:
        return _read_array(file)
    return _read_struct(file, SCALAR_FORMATS[value_type])


def _read_array(file: BinaryIO) -> tuple[object, ...]:
    item_type = GgufValueType(_read_uint32(file))
    item_count = _read_uint64(file)
    return tuple(_read_value(file, item_type) for _ in range(item_count))


def _read_string(file: BinaryIO) -> str:
    byte_count = _read_uint64(file)
    return file.read(byte_count).decode("utf-8")


def _read_struct(file: BinaryIO, fmt: str) -> int | float | bool:
    size = struct.calcsize(fmt)
    data = file.read(size)
    if len(data) != size:
        msg = "Unexpected end of GGUF metadata."
        raise GgufMetadataError(msg)
    return struct.unpack(fmt, data)[0]


def _read_uint32(file: BinaryIO) -> int:
    return cast("int", _read_struct(file, "<I"))


def _read_uint64(file: BinaryIO) -> int:
    return cast("int", _read_struct(file, "<Q"))


def _optional_float(metadata: dict[str, object], *keys: str) -> float | None:
    value = _first_present(metadata, *keys)
    return float(value) if isinstance(value, int | float) else None


def _optional_int(metadata: dict[str, object], *keys: str) -> int | None:
    value = _first_present(metadata, *keys)
    return int(value) if isinstance(value, int) else None


def _first_present(metadata: dict[str, object], *keys: str) -> object | None:
    for key in keys:
        if key in metadata:
            return metadata[key]
    return None

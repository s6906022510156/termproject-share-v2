"""Low level binary storage: fixed headers, struct I/O, seek, free list, checks.

Layout of every binary file:

    [ fixed binary header ][ record 0 ][ record 1 ] ... [ record n ]

    offset(index) = HEADER_SIZE + index * RECORD_SIZE
"""

from __future__ import annotations

import bisect
import struct
from pathlib import Path

import config
from utils import ensure_directory, file_size, flush_and_sync


class StorageError(Exception):
    """Base class for storage problems."""


class CorruptFileError(StorageError):
    """Raised when a binary file fails validation; the file is never changed."""

    def __init__(self, path: Path, message: str, expected: str = "", detected: str = ""):
        self.path = Path(path)
        self.expected = expected
        self.detected = detected
        lines = [
            f"ERROR: {self.path.name} appears to be corrupted.",
            f"Reason          : {message}",
        ]
        if expected:
            lines.append(f"Expected        : {expected}")
        if detected:
            lines.append(f"Detected        : {detected}")
        lines.append("The file was NOT modified. Restore a backup or move the file aside.")
        super().__init__("\n".join(lines))


class BinaryFile:
    """A single binary file made of a fixed header plus fixed length records."""

    def __init__(self, path, record_format: str, magic: bytes, label: str):
        if len(magic) != 8:
            raise StorageError("magic number must be exactly 8 bytes")
        self.path = Path(path)
        self.label = label
        self.record_format = record_format
        self.record_size = struct.calcsize(record_format)
        self.magic = magic
        self.version = config.FILE_VERSION
        self.header_size = config.HEADER_SIZE
        self.record_count = 0
        self.free_count = 0
        self.is_new = False
        self._handle = None
        self._free_slots: list[int] = []

    def __enter__(self):
        return self.open()

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    @property
    def is_open(self) -> bool:
        return self._handle is not None and not self._handle.closed

    def __repr__(self) -> str:
        return (
            f"<{type(self).__name__} {self.path.name} records={self.record_count} "
            f"free={self.free_count} record_size={self.record_size}>"
        )

    def offset_of(self, index: int) -> int:
        """Return the byte offset of record `index`."""
        if index < 0:
            raise StorageError("record index cannot be negative")
        return self.header_size + index * self.record_size

    def build_header(self, record_count: int, free_count: int) -> bytes:
        """Pack the fixed size binary header."""
        return struct.pack(
            config.HEADER_FORMAT,
            self.magic,
            self.version,
            self.header_size,
            self.record_size,
            int(record_count),
            int(free_count),
        )

    def parse_header(self, raw: bytes) -> dict:
        """Unpack a header blob into a dictionary."""
        if len(raw) != self.header_size:
            raise CorruptFileError(
                self.path,
                "header size mismatch",
                expected=f"{self.header_size} bytes",
                detected=f"{len(raw)} bytes",
            )
        values = struct.unpack(config.HEADER_FORMAT, raw)
        return dict(zip(config.HEADER_FIELDS, values))

    def open(self, create: bool = True) -> "BinaryFile":
        """Open an existing file for validation or create a fresh one."""
        ensure_directory(self.path.parent)
        if self.path.exists():
            if file_size(self.path) == 0:
                self._create(create)
            else:
                self._open_existing()
        else:
            if not create:
                raise StorageError(f"{self.path} does not exist")
            self._create(create)
        return self

    def _open_existing(self) -> None:
        header = self._read_and_validate()
        self._handle = open(self.path, "r+b")
        self.record_count = int(header["record_count"])
        self.free_count = int(header["free_count"])

    def _create(self, create: bool) -> None:
        if not create:
            raise StorageError(f"{self.path} does not exist")
        self._handle = open(self.path, "w+b")
        self.record_count = 0
        self.free_count = 0
        self._write_header()
        self.is_new = True

    def _read_and_validate(self) -> dict:
        with open(self.path, "rb") as probe:
            raw = probe.read(self.header_size)
        header = self.parse_header(raw)
        self._validate_header_fields(header)
        self._validate_file_size(header)
        return header

    def _validate_header_fields(self, header: dict) -> None:
        if header["magic"] != self.magic:
            raise CorruptFileError(
                self.path,
                "magic number does not match this file type",
                expected=repr(self.magic),
                detected=repr(header["magic"]),
            )
        if int(header["version"]) != config.FILE_VERSION:
            raise CorruptFileError(
                self.path,
                "unsupported file version",
                expected=f"version {config.FILE_VERSION}",
                detected=f"version {int(header['version'])}",
            )
        if int(header["header_size"]) != self.header_size:
            raise CorruptFileError(
                self.path,
                "header size mismatch",
                expected=f"{self.header_size}",
                detected=f"{int(header['header_size'])}",
            )
        if int(header["record_size"]) != self.record_size:
            raise CorruptFileError(
                self.path,
                "wrong record size",
                expected=f"record size {self.record_size} ({self.record_format})",
                detected=f"record size {int(header['record_size'])}",
            )

    def _validate_file_size(self, header: dict = None) -> None:
        size = file_size(self.path)
        if size < self.header_size:
            raise CorruptFileError(
                self.path,
                "file is shorter than its own header",
                expected=f"at least {self.header_size} bytes",
                detected=f"{size} bytes",
            )
        body = size - self.header_size
        if body % self.record_size != 0:
            raise CorruptFileError(
                self.path,
                "detected incomplete (truncated) record",
                expected=f"a multiple of {self.record_size} bytes after the header",
                detected=f"{body} trailing bytes",
            )
        if header is None:
            header = self.read_header()
        stored = int(header["record_count"])
        actual = body // self.record_size
        if stored != actual:
            raise CorruptFileError(
                self.path,
                "unexpected file size: header record count disagrees with the file",
                expected=f"{stored} records",
                detected=f"{actual} records on disk",
            )
        if int(header["free_count"]) > actual:
            raise CorruptFileError(
                self.path,
                "free slot count is larger than the number of records",
                expected=f"at most {actual}",
                detected=f"{int(header['free_count'])}",
            )

    def _write_header(self) -> None:
        self._handle.seek(0)
        self._handle.write(self.build_header(self.record_count, self.free_count))
        self._handle.flush()

    def write_header(self) -> None:
        """Rewrite the header (record count / free count) and flush."""
        if not self.is_open:
            raise StorageError(f"{self.label} file is not open")
        self._write_header()

    def _require_open(self) -> None:
        if not self.is_open:
            raise StorageError(f"{self.label} file is not open")

    def read_raw(self, index: int) -> bytes:
        """Read exactly one raw record using seek() (random access)."""
        self._require_open()
        if index >= self.record_count:
            raise StorageError(
                f"record index {index} is out of range (file holds {self.record_count} records)"
            )
        self._handle.seek(self.offset_of(index))
        data = self._handle.read(self.record_size)
        if len(data) != self.record_size:
            raise CorruptFileError(
                self.path,
                f"record {index} could not be read completely",
                expected=f"{self.record_size} bytes",
                detected=f"{len(data)} bytes",
            )
        return data

    def write_raw(self, index: int, data: bytes) -> None:
        """Write exactly one raw record in place, keeping the file length fixed."""
        self._require_open()
        if len(data) != self.record_size:
            raise StorageError(
                f"record must be exactly {self.record_size} bytes, got {len(data)}"
            )
        self._handle.seek(self.offset_of(index))
        self._handle.write(data)
        if index >= self.record_count:
            self.record_count = index + 1
            self._write_header()
        self._handle.flush()

    def iter_raw(self, skip: int = 0):
        """Yield (index, raw_bytes) sequentially, decoding nothing."""
        self._require_open()
        if skip >= self.record_count:
            return
        self._handle.seek(self.offset_of(skip))
        for index in range(skip, self.record_count):
            data = self._handle.read(self.record_size)
            if len(data) != self.record_size:
                raise CorruptFileError(
                    self.path,
                    f"record {index} could not be read completely",
                    expected=f"{self.record_size} bytes",
                    detected=f"{len(data)} bytes",
                )
            yield index, data

    def read_header(self) -> dict:
        """Return a copy of the header currently stored on disk."""
        self._require_open()
        self._handle.seek(0)
        return self.parse_header(self._handle.read(self.header_size))

    def verify(self) -> dict:
        """Re-validate the on-disk header and return it."""
        self._require_open()
        self._handle.flush()
        self._validate_header_fields(self.read_header())
        self._validate_file_size()
        return self.read_header()

    def physical_size(self) -> int:
        """Return the current byte size of the file."""
        return file_size(self.path)

    def expected_size(self, record_count: int = None) -> int:
        """Return the byte size the file should have for a record count."""
        count = self.record_count if record_count is None else record_count
        return self.header_size + count * self.record_size

    def flush(self) -> None:
        """Flush buffered writes."""
        if self.is_open:
            self._handle.flush()

    def sync(self) -> None:
        """Flush and force the data to the storage device."""
        if self.is_open:
            flush_and_sync(self._handle)

    def close(self, sync: bool = True) -> None:
        """Flush, update the header, sync and close the file."""
        if not self.is_open:
            return
        if sync:
            self._write_header()
            flush_and_sync(self._handle)
        else:
            self._handle.flush()
        self._handle.close()


class RecordFile(BinaryFile):
    """Random access table with reusable free slots (equipment/category)."""

    def free_slots(self) -> list[int]:
        """Return a copy of the free slot list (lowest slot first)."""
        return list(self._free_slots)

    def rebuild_free_slots(self, free_indexes) -> None:
        """Rebuild the in-memory free list from the status byte of each record."""
        self._free_slots = sorted({int(i) for i in free_indexes})
        self.free_count = len(self._free_slots)
        self._write_header()

    def is_free_slot(self, index: int) -> bool:
        position = bisect.bisect_left(self._free_slots, index)
        return (
            position < len(self._free_slots)
            and self._free_slots[position] == int(index)
        )

    def allocate_slot(self) -> int:
        """Return a free slot index, or the next appended index when full."""
        if self._free_slots:
            index = self._free_slots.pop(0)
            self.free_count = len(self._free_slots)
            return index
        return self.record_count

    def release_slot(self, index: int) -> None:
        """Mark a slot as free and remember it for later reuse."""
        position = bisect.bisect_left(self._free_slots, index)
        if position >= len(self._free_slots) or self._free_slots[position] != index:
            self._free_slots.insert(position, int(index))
        self.free_count = len(self._free_slots)
        self._write_header()

    def write_record(self, index: int, data: bytes) -> None:
        """Write a record; a slot that was free becomes used again."""
        self.write_raw(index, data)
        if self.is_free_slot(index):
            position = bisect.bisect_left(self._free_slots, index)
            self._free_slots.pop(position)
            self.free_count = len(self._free_slots)
            self._write_header()


class MovementLog(BinaryFile):
    """Append only history log (movement.dat)."""

    def append(self, data: bytes) -> int:
        """Append one record at the end of the log and return its index."""
        self._require_open()
        if len(data) != self.record_size:
            raise StorageError(
                f"record must be exactly {self.record_size} bytes, got {len(data)}"
            )
        index = self.record_count
        self._handle.seek(self.offset_of(index))
        self._handle.write(data)
        self.record_count = index + 1
        self._write_header()
        return index

    def read_recent(self, count: int) -> list[bytes]:
        """Return the last `count` records as raw bytes, oldest first."""
        if count <= 0 or self.record_count == 0:
            return []
        first = max(0, self.record_count - count)
        return [data for _, data in self.iter_raw(first)]

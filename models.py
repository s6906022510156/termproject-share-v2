"""In-memory models with struct based (un)packing for fixed length records."""

from __future__ import annotations

import struct
from dataclasses import dataclass

import config
from utils import decode_fixed_string, encode_fixed_string


class RecordError(ValueError):
    """Raised when raw bytes cannot be interpreted as a record."""


@dataclass
class Equipment:
    """One network equipment record (116 bytes in equipment.dat)."""

    equipment_id: int
    category_id: int
    hostname: str
    brand: str
    model: str
    serial_no: str
    location: str
    status: int = config.STATUS_ACTIVE
    price: float = 0.0

    @property
    def is_free(self) -> bool:
        return int(self.status) == config.STATUS_FREE

    @property
    def is_live(self) -> bool:
        return not self.is_free

    @property
    def status_name(self) -> str:
        return config.status_name(self.status)

    def to_bytes(self) -> bytes:
        """Serialise to exactly EQUIPMENT_SIZE bytes with struct.pack()."""
        data = struct.pack(
            config.EQUIPMENT_FORMAT,
            int(self.equipment_id),
            int(self.category_id),
            encode_fixed_string(self.hostname, config.FIELD_SIZES["hostname"]),
            encode_fixed_string(self.brand, config.FIELD_SIZES["brand"]),
            encode_fixed_string(self.model, config.FIELD_SIZES["model"]),
            encode_fixed_string(self.serial_no, config.FIELD_SIZES["serial_no"]),
            encode_fixed_string(self.location, config.FIELD_SIZES["location"]),
            int(self.status),
            float(self.price),
        )
        if len(data) != config.EQUIPMENT_SIZE:
            raise RecordError(
                f"packed equipment record is {len(data)} bytes, expected {config.EQUIPMENT_SIZE}"
            )
        return data

    @classmethod
    def from_bytes(cls, data: bytes) -> "Equipment":
        """Deserialise EQUIPMENT_SIZE bytes with struct.unpack()."""
        if len(data) != config.EQUIPMENT_SIZE:
            raise RecordError(
                f"equipment record must be {config.EQUIPMENT_SIZE} bytes, got {len(data)}"
            )
        values = struct.unpack(config.EQUIPMENT_FORMAT, data)
        return cls(
            equipment_id=values[0],
            category_id=values[1],
            hostname=decode_fixed_string(values[2]),
            brand=decode_fixed_string(values[3]),
            model=decode_fixed_string(values[4]),
            serial_no=decode_fixed_string(values[5]),
            location=decode_fixed_string(values[6]),
            status=values[7],
            price=round(float(values[8]), 2),
        )

    def detail_lines(self, category_name: str = "") -> list[str]:
        """Return the vertical detail view used by 'View One'."""
        return [
            f"Equipment ID : {self.equipment_id}",
            f"Category     : {category_name or self.category_id}",
            f"Hostname     : {self.hostname}",
            f"Brand        : {self.brand}",
            f"Model        : {self.model}",
            f"Serial No    : {self.serial_no}",
            f"Location     : {self.location}",
            f"Status       : {self.status_name}",
            f"Price        : {self.price:,.2f}",
        ]

    def table_row(self, category_name: str = "") -> str:
        """Return the one-line row used by 'View All' and the filters."""
        from utils import pad

        return (
            f"{pad(self.equipment_id, 8)}"
            f"{pad(category_name or self.category_id, 15)}"
            f"{pad(self.hostname, 21)}"
            f"{pad(self.brand, 17)}"
            f"{pad(self.model, 21)}"
            f"{pad(self.serial_no, 21)}"
            f"{pad(self.location, 25)}"
            f"{pad(self.status_name, 13)}"
            f"{pad(f'{self.price:,.2f}', 14)}"
        )

    @staticmethod
    def table_header() -> str:
        from utils import pad

        return (
            f"{pad('ID', 8)}{pad('Category', 15)}{pad('Hostname', 21)}"
            f"{pad('Brand', 17)}{pad('Model', 21)}{pad('Serial No', 21)}"
            f"{pad('Location', 25)}{pad('Status', 13)}{pad('Price', 14)}"
        )


@dataclass
class Category:
    """One category record (68 bytes in category.dat)."""

    category_id: int
    category_name: str
    description: str = ""
    status: int = config.CATEGORY_ACTIVE

    @property
    def is_active(self) -> bool:
        return int(self.status) == config.CATEGORY_ACTIVE

    @property
    def status_name(self) -> str:
        return config.CATEGORY_STATUS_NAMES.get(int(self.status), "Unknown")

    def to_bytes(self) -> bytes:
        """Serialise to exactly CATEGORY_SIZE bytes with struct.pack()."""
        data = struct.pack(
            config.CATEGORY_FORMAT,
            int(self.category_id),
            encode_fixed_string(self.category_name, config.FIELD_SIZES["category_name"]),
            encode_fixed_string(self.description, config.FIELD_SIZES["description"]),
            int(self.status),
        )
        if len(data) != config.CATEGORY_SIZE:
            raise RecordError(
                f"packed category record is {len(data)} bytes, expected {config.CATEGORY_SIZE}"
            )
        return data

    @classmethod
    def from_bytes(cls, data: bytes) -> "Category":
        """Deserialise CATEGORY_SIZE bytes with struct.unpack()."""
        if len(data) != config.CATEGORY_SIZE:
            raise RecordError(
                f"category record must be {config.CATEGORY_SIZE} bytes, got {len(data)}"
            )
        values = struct.unpack(config.CATEGORY_FORMAT, data)
        return cls(
            category_id=values[0],
            category_name=decode_fixed_string(values[1]),
            description=decode_fixed_string(values[2]),
            status=values[3],
        )


@dataclass
class Movement:
    """One operation history record (48 bytes in movement.dat)."""

    timestamp: int
    op_code: int
    equipment_id: int
    status_after: int = config.STATUS_ACTIVE
    location_after: str = ""
    price_after: float = 0.0

    @property
    def op_name(self) -> str:
        return config.op_name(self.op_code)

    @property
    def status_name(self) -> str:
        return config.status_name(self.status_after)

    def to_bytes(self) -> bytes:
        """Serialise to exactly MOVEMENT_SIZE bytes with struct.pack()."""
        data = struct.pack(
            config.MOVEMENT_FORMAT,
            int(self.timestamp),
            int(self.op_code),
            int(self.equipment_id),
            int(self.status_after),
            encode_fixed_string(
                self.location_after, config.FIELD_SIZES["location_after"]
            ),
            float(self.price_after),
        )
        if len(data) != config.MOVEMENT_SIZE:
            raise RecordError(
                f"packed movement record is {len(data)} bytes, expected {config.MOVEMENT_SIZE}"
            )
        return data

    @classmethod
    def from_bytes(cls, data: bytes) -> "Movement":
        """Deserialise MOVEMENT_SIZE bytes with struct.unpack()."""
        if len(data) != config.MOVEMENT_SIZE:
            raise RecordError(
                f"movement record must be {config.MOVEMENT_SIZE} bytes, got {len(data)}"
            )
        values = struct.unpack(config.MOVEMENT_FORMAT, data)
        return cls(
            timestamp=values[0],
            op_code=values[1],
            equipment_id=values[2],
            status_after=values[3],
            location_after=decode_fixed_string(values[4]),
            price_after=round(float(values[5]), 2),
        )

    def line(self) -> str:
        """Return the activity line used by the report and the history view."""
        from utils import format_timestamp, pad

        return (
            f"{pad(format_timestamp(self.timestamp), 20)}"
            f"{pad(self.op_name, 10)}"
            f"{pad(f'Equipment {self.equipment_id}', 22)}"
            f"{pad(self.status_name, 14)}"
            f"{pad(self.location_after, 25)}"
            f"{self.price_after:,.2f}"
        )

    @staticmethod
    def line_header() -> str:
        from utils import pad

        return (
            f"{pad('Timestamp', 20)}{pad('Operation', 10)}{pad('Reference', 22)}"
            f"{pad('Status After', 14)}{pad('Location After', 25)}{'Price After'}"
        )

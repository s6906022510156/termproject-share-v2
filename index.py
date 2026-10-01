"""In-memory index: equipment_id -> record index (rebuilt from equipment.dat).

The index lives in memory only; it is never written to an extra binary file.
"""

from __future__ import annotations

import config
from models import Equipment


class EquipmentIndex:
    """Mapping of live equipment_id values to their record position."""

    def __init__(self):
        self._positions: dict[int, int] = {}

    def __len__(self) -> int:
        return len(self._positions)

    def __contains__(self, equipment_id: object) -> bool:
        try:
            return int(equipment_id) in self._positions
        except (TypeError, ValueError):
            return False

    def __repr__(self) -> str:
        return f"<EquipmentIndex entries={len(self._positions)}>"

    def clear(self) -> None:
        """Drop every index entry."""
        self._positions.clear()

    def rebuild(self, record_file) -> int:
        """Rebuild the whole index by scanning equipment.dat once."""
        self.clear()
        duplicates = []
        for index, raw in record_file.iter_raw():
            equipment = Equipment.from_bytes(raw)
            if not equipment.is_live:
                continue
            if equipment.equipment_id in self._positions:
                duplicates.append(equipment.equipment_id)
                continue
            self._positions[equipment.equipment_id] = index
        if duplicates:
            raise ValueError(
                "duplicate active equipment_id found while rebuilding the index: "
                + ", ".join(str(item) for item in sorted(set(duplicates)))
            )
        return len(self._positions)

    def add(self, equipment_id: int, position: int) -> None:
        """Register (or move) the entry for an equipment_id."""
        self._positions[int(equipment_id)] = int(position)

    def remove(self, equipment_id: int) -> None:
        """Remove the entry of a deleted equipment."""
        self._positions.pop(int(equipment_id), None)

    def move(self, equipment_id: int, position: int) -> None:
        """Update the stored position of an existing entry."""
        self._positions[int(equipment_id)] = int(position)

    def get(self, equipment_id) -> int | None:
        """Return the record position of an equipment_id, or None."""
        try:
            return self._positions.get(int(equipment_id))
        except (TypeError, ValueError):
            return None

    def offset_of(self, equipment_id) -> int | None:
        """Return the byte offset of an equipment_id, or None."""
        position = self.get(equipment_id)
        if position is None:
            return None
        return config.HEADER_SIZE + position * config.EQUIPMENT_SIZE

    def contains(self, equipment_id) -> bool:
        """Return True when the equipment_id is present in the index."""
        return self.get(equipment_id) is not None

    def ids(self) -> list[int]:
        """Return every indexed equipment_id, sorted."""
        return sorted(self._positions)

    def items(self) -> list[tuple[int, int]]:
        """Return sorted (equipment_id, position) pairs."""
        return sorted(self._positions.items())

    def verify(self, record_file) -> list[str]:
        """Check every index entry against the file and return a problem list."""
        problems: list[str] = []
        if len(self._positions) > record_file.record_count:
            problems.append("index holds more entries than the file has records")
        for equipment_id, position in self.items():
            if position < 0 or position >= record_file.record_count:
                problems.append(
                    f"equipment {equipment_id}: position {position} is out of range"
                )
                continue
            equipment = Equipment.from_bytes(record_file.read_raw(position))
            if equipment.equipment_id != equipment_id:
                problems.append(
                    f"equipment {equipment_id}: record {position} holds "
                    f"{equipment.equipment_id}"
                )
            if equipment.is_free:
                problems.append(f"equipment {equipment_id}: record {position} is free")
        return problems

"""Database facade: owns the three binary files, the index, and safe shutdown."""

from __future__ import annotations

from pathlib import Path

import config
from index import EquipmentIndex
from models import Category, Equipment
from storage import CorruptFileError, MovementLog, RecordFile, StorageError
from utils import ensure_directory


class InventoryDatabase:
    """Opens, initialises and closes every binary file of the system."""

    def __init__(self, base_dir=None):
        self.base_dir = Path(base_dir) if base_dir else config.BASE_DIR
        self.data_dir = self.base_dir / "data"
        self.report_path = self.base_dir / config.REPORT_PATH.name
        self.equipment_file: RecordFile | None = None
        self.category_file: RecordFile | None = None
        self.movement_file: MovementLog | None = None
        self.index = EquipmentIndex()
        self.categories: dict[int, Category] = {}
        self.created_files: list[str] = []

    def __enter__(self):
        return self.open()

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    @property
    def is_open(self) -> bool:
        return bool(
            self.equipment_file
            and self.equipment_file.is_open
            and self.category_file
            and self.category_file.is_open
            and self.movement_file
            and self.movement_file.is_open
        )

    def open(self) -> "InventoryDatabase":
        """Create missing files, validate existing ones, rebuild the index."""
        ensure_directory(self.data_dir)
        self.equipment_file = RecordFile(
            self.data_dir / config.EQUIPMENT_FILE_NAME,
            config.EQUIPMENT_FORMAT,
            config.EQUIPMENT_MAGIC,
            "Equipment",
        )
        self.category_file = RecordFile(
            self.data_dir / config.CATEGORY_FILE_NAME,
            config.CATEGORY_FORMAT,
            config.CATEGORY_MAGIC,
            "Category",
        )
        self.movement_file = MovementLog(
            self.data_dir / config.MOVEMENT_FILE_NAME,
            config.MOVEMENT_FORMAT,
            config.MOVEMENT_MAGIC,
            "Movement",
        )
        try:
            for binary_file in (self.equipment_file, self.category_file, self.movement_file):
                binary_file.open(create=True)
                if binary_file.is_new:
                    self.created_files.append(binary_file.path.name)
            self._rebuild_runtime_state()
        except Exception:
            self.close()
            raise
        return self

    def _rebuild_runtime_state(self) -> None:
        free_slots = []
        for position, raw in self.equipment_file.iter_raw():
            equipment = Equipment.from_bytes(raw)
            if equipment.is_free:
                free_slots.append(position)
        self.equipment_file.rebuild_free_slots(free_slots)
        self.index.rebuild(self.equipment_file)
        self.categories = {}
        for _, raw in self.category_file.iter_raw():
            category = Category.from_bytes(raw)
            self.categories[category.category_id] = category
        self._ensure_default_categories()

    def _ensure_default_categories(self) -> None:
        for category_id, name, description in config.DEFAULT_CATEGORIES:
            if category_id in self.categories:
                continue
            slot = self.category_file.allocate_slot()
            category = Category(
                category_id=category_id,
                category_name=name,
                description=description,
                status=config.CATEGORY_ACTIVE,
            )
            self.category_file.write_record(slot, category.to_bytes())
            self.categories[category_id] = category

    def register_category(self, category: Category) -> int:
        """Store a category record and cache it in memory."""
        if category.category_id in self.categories:
            raise ValueError(f"category {category.category_id} already exists")
        slot = self.category_file.allocate_slot()
        self.category_file.write_record(slot, category.to_bytes())
        self.categories[category.category_id] = category
        return slot

    def flush(self) -> None:
        """Flush every open file."""
        for binary_file in self._files():
            binary_file.flush()

    def sync(self) -> None:
        """Write headers, flush and fsync every open file."""
        for binary_file in self._files():
            if binary_file.is_open:
                binary_file.close(sync=True)

    def close(self) -> None:
        """Safe exit: update headers, flush, fsync, then close the files."""
        for binary_file in self._files():
            if binary_file is not None and binary_file.is_open:
                binary_file.close(sync=True)
        self.equipment_file = None
        self.category_file = None
        self.movement_file = None

    def _files(self):
        return (self.equipment_file, self.category_file, self.movement_file)

    def status_lines(self) -> list[str]:
        """Return a short startup summary of the opened files."""
        lines = []
        for binary_file in self._files():
            lines.append(
                f"{binary_file.path.name:<14} records={binary_file.record_count:<5} "
                f"record_size={binary_file.record_size} "
                f"size={binary_file.physical_size()} bytes"
            )
        return lines

    def index_problems(self) -> list[str]:
        """Return index inconsistencies detected by a full verify pass."""
        return self.index.verify(self.equipment_file)


__all__ = [
    "InventoryDatabase",
    "CorruptFileError",
    "StorageError",
]

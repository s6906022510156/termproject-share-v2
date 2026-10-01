"""Business logic: Add, Update, Delete, View, Filter, Statistics, activity log."""

from __future__ import annotations

from dataclasses import replace

import config
from models import Category, Equipment, Movement
from utils import now_timestamp
from validation import (
    ValidationError,
    validate_category_id,
    validate_equipment_id,
    validate_fixed_text,
    validate_integer_field,
    validate_price,
    validate_status,
)


class NotFoundError(LookupError):
    """Raised when an equipment or category does not exist."""


class DuplicateError(ValidationError):
    """Raised when a unique id is reused by a live record."""


class InventoryService:
    """All inventory operations on top of the binary storage layer."""

    def __init__(self, database):
        self.db = database

    @property
    def equipment_file(self):
        return self.db.equipment_file

    @property
    def category_file(self):
        return self.db.category_file

    @property
    def movement_file(self):
        return self.db.movement_file

    @property
    def index(self):
        return self.db.index

    def log_movement(
        self,
        op_code: int,
        equipment_id: int,
        status_after: int,
        location_after: str,
        price_after: float,
    ) -> int:
        """Append one operation record to movement.dat."""
        movement = Movement(
            timestamp=now_timestamp(),
            op_code=op_code,
            equipment_id=equipment_id,
            status_after=status_after,
            location_after=location_after,
            price_after=price_after,
        )
        return self.movement_file.append(movement.to_bytes())

    def category_name(self, category_id: int) -> str:
        category = self.db.categories.get(int(category_id))
        return category.category_name if category else ""

    def list_categories(self, active_only: bool = True) -> list[Category]:
        categories = sorted(self.db.categories.values(), key=lambda item: item.category_id)
        if active_only:
            return [item for item in categories if item.is_active]
        return categories

    def category_ids(self, active_only: bool = True) -> list[int]:
        return [item.category_id for item in self.list_categories(active_only)]

    def add_category(
        self,
        category_id: int,
        category_name: str,
        description: str = "",
        status: int = config.CATEGORY_ACTIVE,
    ) -> int:
        """Add a category record (used by the tests and future menus)."""
        category_id = validate_integer_field(
            category_id, "category id", config.CATEGORY_ID_MIN, config.CATEGORY_ID_MAX
        )
        if category_id in self.db.categories:
            raise DuplicateError(f"category id {category_id} already exists")
        category = Category(
            category_id=category_id,
            category_name=validate_fixed_text(category_name, "category_name"),
            description=validate_fixed_text(description, "description")
            if description
            else "",
            status=validate_integer_field(
                status, "category status", 0, 1
            ),
        )
        return self.db.register_category(category)

    def _prepare_fields(
        self,
        equipment_id,
        category_id,
        hostname,
        brand,
        model,
        serial_no,
        location,
        status,
        price,
    ) -> Equipment:
        allowed = self.category_ids(active_only=True)
        if not allowed:
            raise ValidationError("no active category is available")
        return Equipment(
            equipment_id=validate_equipment_id(equipment_id),
            category_id=validate_category_id(category_id, allowed),
            hostname=validate_fixed_text(hostname, "hostname"),
            brand=validate_fixed_text(brand, "brand"),
            model=validate_fixed_text(model, "model"),
            serial_no=validate_fixed_text(serial_no, "serial_no"),
            location=validate_fixed_text(location, "location"),
            status=validate_status(status),
            price=validate_price(price),
        )

    def add_equipment(
        self,
        equipment_id,
        category_id,
        hostname,
        brand,
        model,
        serial_no,
        location,
        status=config.STATUS_ACTIVE,
        price=0.0,
    ) -> tuple[Equipment, int]:
        """Validate, store, index and log a new equipment record."""
        equipment = self._prepare_fields(
            equipment_id,
            category_id,
            hostname,
            brand,
            model,
            serial_no,
            location,
            status,
            price,
        )
        if self.index.contains(equipment.equipment_id):
            raise DuplicateError(
                f"equipment id {equipment.equipment_id} already exists"
            )
        slot = self.equipment_file.allocate_slot()
        self.equipment_file.write_record(slot, equipment.to_bytes())
        self.index.add(equipment.equipment_id, slot)
        self.log_movement(
            config.OP_ADD,
            equipment.equipment_id,
            equipment.status,
            equipment.location,
            equipment.price,
        )
        return equipment, slot

    def update_equipment(self, equipment_id, **changes) -> Equipment:
        """Rewrite an existing record in place, then log the operation."""
        equipment = self.get_equipment(equipment_id, log_view=False)
        if equipment is None:
            raise NotFoundError(f"equipment {equipment_id} does not exist")
        slot = self.index.get(equipment.equipment_id)
        if slot is None:
            raise NotFoundError(f"equipment {equipment_id} is not in the index")
        changes.pop("equipment_id", None)
        checked = self._prepare_fields(
            equipment.equipment_id,
            changes.get("category_id", equipment.category_id),
            changes.get("hostname", equipment.hostname),
            changes.get("brand", equipment.brand),
            changes.get("model", equipment.model),
            changes.get("serial_no", equipment.serial_no),
            changes.get("location", equipment.location),
            changes.get("status", equipment.status),
            changes.get("price", equipment.price),
        )
        self.equipment_file.write_record(slot, checked.to_bytes())
        self.index.move(checked.equipment_id, slot)
        self.log_movement(
            config.OP_UPDATE,
            checked.equipment_id,
            checked.status,
            checked.location,
            checked.price,
        )
        return checked

    def delete_equipment(self, equipment_id) -> Equipment:
        """Mark a record as deleted/free without shrinking the file."""
        equipment = self.get_equipment(equipment_id, log_view=False)
        if equipment is None:
            raise NotFoundError(f"equipment {equipment_id} does not exist")
        slot = self.index.get(equipment.equipment_id)
        deleted = replace(equipment, status=config.STATUS_FREE)
        self.equipment_file.write_record(slot, deleted.to_bytes())
        self.equipment_file.release_slot(slot)
        self.index.remove(deleted.equipment_id)
        self.log_movement(
            config.OP_DELETE,
            deleted.equipment_id,
            deleted.status,
            deleted.location,
            deleted.price,
        )
        return deleted

    def get_equipment(self, equipment_id, log_view: bool = True) -> Equipment | None:
        """Read one record through the index and seek()."""
        slot = self.index.get(equipment_id)
        if slot is None:
            return None
        equipment = Equipment.from_bytes(self.equipment_file.read_raw(slot))
        if equipment.is_free:
            self.index.remove(equipment.equipment_id)
            return None
        if log_view:
            self.log_movement(
                config.OP_VIEW,
                equipment.equipment_id,
                equipment.status,
                equipment.location,
                equipment.price,
            )
        return equipment

    def equipment_exists(self, equipment_id) -> bool:
        return self.index.contains(equipment_id)

    def iter_records(self, include_free: bool = False):
        """Yield (slot, Equipment) for every record in the file."""
        for slot, raw in self.equipment_file.iter_raw():
            equipment = Equipment.from_bytes(raw)
            if equipment.is_free and not include_free:
                continue
            yield slot, equipment

    def view_all(self) -> list[Equipment]:
        return [equipment for _, equipment in self.iter_records()]

    def view_deleted(self) -> list[Equipment]:
        return [
            equipment
            for _, equipment in self.iter_records(include_free=True)
            if equipment.is_free
        ]

    def filter_equipment(
        self,
        category_id=None,
        brand=None,
        location=None,
        status=None,
        text=None,
    ) -> list[Equipment]:
        """Filter active equipment; every criterion is optional and combined."""
        results = []
        brand_key = brand.strip().lower() if brand else None
        location_key = location.strip().lower() if location else None
        text_key = text.strip().lower() if text else None
        for _, equipment in self.iter_records():
            if category_id is not None and equipment.category_id != int(category_id):
                continue
            if status is not None and equipment.status != int(status):
                continue
            if brand_key and brand_key not in equipment.brand.lower():
                continue
            if location_key and location_key not in equipment.location.lower():
                continue
            if text_key and text_key not in equipment.hostname.lower():
                continue
            results.append(equipment)
        return results

    def statistics(self) -> dict:
        """Compute the numbers used by the statistics screen and the report."""
        by_category: dict[int, int] = {cid: 0 for cid in self.category_ids(False)}
        by_status: dict[int, int] = {}
        by_location: dict[str, int] = {}
        by_brand: dict[str, int] = {}
        live_total = 0
        free_total = 0
        active_value = 0.0
        active_price_total = 0.0
        slots = self.equipment_file.record_count
        for _, equipment in self.iter_records(include_free=True):
            if equipment.is_free:
                free_total += 1
                continue
            live_total += 1
            by_category[equipment.category_id] = by_category.get(equipment.category_id, 0) + 1
            by_status[equipment.status] = by_status.get(equipment.status, 0) + 1
            by_location[equipment.location] = by_location.get(equipment.location, 0) + 1
            by_brand[equipment.brand] = by_brand.get(equipment.brand, 0) + 1
            active_price_total += equipment.price
            if equipment.status == config.STATUS_ACTIVE:
                active_value += equipment.price
        return {
            "total_equipment": live_total,
            "total_records": slots,
            "active": by_status.get(config.STATUS_ACTIVE, 0),
            "maintenance": by_status.get(config.STATUS_MAINTENANCE, 0),
            "retired": by_status.get(config.STATUS_RETIRED, 0),
            "spare": by_status.get(config.STATUS_SPARE, 0),
            "deleted": free_total,
            "free_slots": self.equipment_file.free_count,
            "used_slots": live_total,
            "by_category": by_category,
            "by_status": by_status,
            "by_location": by_location,
            "by_brand": by_brand,
            "total_value": active_value,
            "average_price": (active_price_total / live_total) if live_total else 0.0,
            "activity_records": self.movement_file.record_count,
        }

    def recent_activity(self, count: int = config.RECENT_ACTIVITY_LIMIT) -> list[Movement]:
        """Return the most recent operation records, oldest first."""
        records = self.movement_file.read_recent(count)
        return [Movement.from_bytes(raw) for raw in records]

    def seed_demo_equipment(self, count: int = 50) -> list[Equipment]:
        """Create `count` demo equipment records (used by tests and --seed)."""
        categories = self.category_ids(active_only=True)
        created = []
        for number in range(1, count + 1):
            category_id = categories[(number - 1) % len(categories)]
            equipment_id = 1000 + number
            if self.index.contains(equipment_id):
                continue
            brand = config.SEED_BRANDS[(number - 1) % len(config.SEED_BRANDS)]
            location = config.SEED_LOCATIONS[(number - 1) % len(config.SEED_LOCATIONS)]
            status = (
                config.STATUS_ACTIVE
                if number % 7
                else config.STATUS_MAINTENANCE
            )
            equipment, _ = self.add_equipment(
                equipment_id=equipment_id,
                category_id=category_id,
                hostname=f"{'SW' if category_id == 1 else 'EQ'}-{equipment_id}",
                brand=brand,
                model=f"MODEL-{equipment_id}",
                serial_no=f"SN{equipment_id:08d}",
                location=location,
                status=status,
                price=1000.0 + number * 137.5,
            )
            created.append(equipment)
        return created

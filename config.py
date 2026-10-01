"""Central configuration: paths, binary record formats, sizes, and code tables.

Every binary format is explicitly Little-Endian (leading "<") and every
fixed-length string field is ASCII padded with b"\x00".
"""

from __future__ import annotations

import struct
from pathlib import Path

APP_NAME = "Network Equipment Inventory System"
APP_VERSION = "1.0"
REPORT_TITLE = "Network Equipment Inventory"

ENDIANNESS = "Little-Endian"
ENCODING = "ASCII"

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
REPORT_PATH = BASE_DIR / "report.txt"

EQUIPMENT_FILE_NAME = "equipment.dat"
CATEGORY_FILE_NAME = "category.dat"
MOVEMENT_FILE_NAME = "movement.dat"

EQUIPMENT_PATH = DATA_DIR / EQUIPMENT_FILE_NAME
CATEGORY_PATH = DATA_DIR / CATEGORY_FILE_NAME
MOVEMENT_PATH = DATA_DIR / MOVEMENT_FILE_NAME

EQUIPMENT_FORMAT = "<II20s16s20s20s24sIf"
CATEGORY_FORMAT = "<I20s40sI"
MOVEMENT_FORMAT = "<QIII24sf"

EQUIPMENT_SIZE = struct.calcsize(EQUIPMENT_FORMAT)
CATEGORY_SIZE = struct.calcsize(CATEGORY_FORMAT)
MOVEMENT_SIZE = struct.calcsize(MOVEMENT_FORMAT)

EXPECTED_EQUIPMENT_SIZE = 116
EXPECTED_CATEGORY_SIZE = 68
EXPECTED_MOVEMENT_SIZE = 48

HEADER_FORMAT = "<8sHHIII"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
EXPECTED_HEADER_SIZE = 24

FILE_VERSION = 1

EQUIPMENT_MAGIC = b"NEQEQP01"
CATEGORY_MAGIC = b"NEQCAT01"
MOVEMENT_MAGIC = b"NEQMOV01"

HEADER_FIELDS = (
    "magic",
    "version",
    "header_size",
    "record_size",
    "record_count",
    "free_count",
)

EQUIPMENT_FIELDS = (
    "equipment_id",
    "category_id",
    "hostname",
    "brand",
    "model",
    "serial_no",
    "location",
    "status",
    "price",
)

CATEGORY_FIELDS = (
    "category_id",
    "category_name",
    "description",
    "status",
)

MOVEMENT_FIELDS = (
    "timestamp",
    "op_code",
    "equipment_id",
    "status_after",
    "location_after",
    "price_after",
)

FIELD_SIZES = {
    "hostname": 20,
    "brand": 16,
    "model": 20,
    "serial_no": 20,
    "location": 24,
    "category_name": 20,
    "description": 40,
    "location_after": 24,
}

STATUS_FREE = 0
STATUS_ACTIVE = 1
STATUS_MAINTENANCE = 2
STATUS_RETIRED = 3
STATUS_SPARE = 4

STATUS_NAMES = {
    STATUS_FREE: "Deleted/Free",
    STATUS_ACTIVE: "Active",
    STATUS_MAINTENANCE: "Maintenance",
    STATUS_RETIRED: "Retired",
    STATUS_SPARE: "Spare",
}

CATEGORY_ACTIVE = 1
CATEGORY_INACTIVE = 0

CATEGORY_STATUS_NAMES = {
    CATEGORY_ACTIVE: "Active",
    CATEGORY_INACTIVE: "Inactive",
}

OP_ADD = 1
OP_UPDATE = 2
OP_DELETE = 3
OP_VIEW = 4

OP_NAMES = {
    OP_ADD: "ADD",
    OP_UPDATE: "UPDATE",
    OP_DELETE: "DELETE",
    OP_VIEW: "VIEW",
}

ID_MIN = 1
ID_MAX = 0xFFFFFFFF
CATEGORY_ID_MIN = 1
CATEGORY_ID_MAX = 0xFFFFFFFF
PRICE_MIN = 0.0
PRICE_MAX = 999_999_999.99

DEFAULT_CATEGORIES = (
    (1, "Switch", "Layer 2 network access switch"),
    (2, "Router", "Layer 3 routing device"),
    (3, "Firewall", "Security gateway appliance"),
    (4, "Access Point", "Wireless access point"),
    (5, "Server", "Rack mounted network server"),
)

PAGE_SIZE = 10
RECENT_ACTIVITY_LIMIT = 10

SEED_BRANDS = ("Cisco", "Juniper", "Arista", "MikroTik", "Ubiquiti", "Fortinet")
SEED_LOCATIONS = (
    "Server Room A",
    "Server Room B",
    "Building 1 Floor 2",
    "Building 2 Floor 1",
    "Data Center 3",
    "Branch Office",
)


def status_name(status: int) -> str:
    """Return the printable name of an equipment status code."""
    return STATUS_NAMES.get(status, f"Unknown({status})")


def op_name(op_code: int) -> str:
    """Return the printable name of an operation code."""
    return OP_NAMES.get(op_code, f"OP{op_code}")

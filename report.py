"""report.txt generation: summary statistics plus recent operation history."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import config
from models import Movement
from utils import format_money, pad, rule


def _section(title: str) -> list[str]:
    return ["", title, rule("-", 40)]


def build_report_lines(service, movement_limit: int = config.RECENT_ACTIVITY_LIMIT) -> list[str]:
    """Build the whole report as a list of text lines."""
    db = service.db
    stats = service.statistics()
    lines = [
        rule("=", 40),
        config.REPORT_TITLE,
        "Summary Report",
        rule("=", 40),
        "",
        f"Generated At : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"App Version  : {config.APP_VERSION}",
        f"Endianness   : {config.ENDIANNESS}",
        f"Encoding     : {config.ENCODING}",
    ]
    lines += _section("Summary")
    lines += [
        f"Total Equipment : {stats['total_equipment']}",
        f"Active          : {stats['active']}",
        f"Maintenance     : {stats['maintenance']}",
        f"Retired         : {stats['retired']}",
        f"Spare           : {stats['spare']}",
        f"Deleted         : {stats['deleted']}",
        f"Free Slots      : {stats['free_slots']}",
        f"Record Slots    : {stats['total_records']}",
        f"Total Value     : {format_money(stats['total_value'])}",
        f"Average Price   : {format_money(stats['average_price'])}",
    ]
    lines += _section("Equipment by Category")
    for category in service.list_categories(active_only=False):
        count = stats["by_category"].get(category.category_id, 0)
        lines.append(
            f"{pad(category.category_name, 20)}: {count}  "
            f"(id {category.category_id}, {category.status_name})"
        )
    lines += _section("Equipment by Status")
    for status_code in sorted(config.STATUS_NAMES):
        count = stats["by_status"].get(status_code, 0)
        lines.append(f"{pad(config.status_name(status_code), 20)}: {count}")
    lines += _section("Equipment by Location")
    for location, count in sorted(stats["by_location"].items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(f"{pad(location or '(unknown)', 25)}: {count}")
    lines += _section("Recent Activity")
    activity = service.recent_activity(movement_limit)
    if not activity:
        lines.append("(no operations recorded yet)")
    else:
        lines.append(f"Operation records in {config.MOVEMENT_FILE_NAME}: {db.movement_file.record_count}")
        lines.append(
            f"Showing the last {len(activity)} operation(s), oldest first."
        )
        lines.append("")
        lines.append(Movement.line_header())
        for movement in activity:
            lines.append(movement.line())
    lines += _section("Binary File Layout")
    for name, binary_file, fields in (
        (config.EQUIPMENT_FILE_NAME, db.equipment_file, config.EQUIPMENT_FIELDS),
        (config.CATEGORY_FILE_NAME, db.category_file, config.CATEGORY_FIELDS),
        (config.MOVEMENT_FILE_NAME, db.movement_file, config.MOVEMENT_FIELDS),
    ):
        lines.append(
            f"{pad(name, 20)}: {pad(binary_file.record_format, 24)} "
            f"{pad(str(binary_file.record_size) + ' bytes/record', 18)} "
            f"records={binary_file.record_count}"
        )
        lines.append(f"{'':20}  fields: {', '.join(fields)}")
    lines.append(
        f"{'Header':<20}: {pad(config.HEADER_FORMAT, 24)} "
        f"{pad(str(config.HEADER_SIZE) + ' bytes/file', 18)} "
        f"fields: {', '.join(config.HEADER_FIELDS)}"
    )
    lines.append(
        f"Note: deleted records are recycled, so the free slot count equals the "
        f"deleted record count in this version."
    )
    lines += ["", rule("=", 40), "End of report", rule("=", 40)]
    return lines


def write_report(path, lines) -> Path:
    """Write the report lines to `path` as plain text."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(lines) + "\n"
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
        handle.flush()
    return path


def generate_report(service, path=None, movement_limit: int = config.RECENT_ACTIVITY_LIMIT) -> Path:
    """Build and store report.txt, returning the file path."""
    target = Path(path) if path else service.db.report_path
    return write_report(target, build_report_lines(service, movement_limit))

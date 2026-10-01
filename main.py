"""Terminal application: startup, main menu, view submenu, safe exit."""

from __future__ import annotations

import argparse
import sys

import config
import report as report_module
from crud import DuplicateError, InventoryService, NotFoundError
from database import InventoryDatabase
from models import Equipment
from storage import CorruptFileError, StorageError
from utils import format_money, pad, rule
from validation import (
    ValidationError,
    read_choice,
    read_float,
    read_int,
    read_line,
    read_non_empty,
    read_optional,
    read_yes_no,
    validate_category_id,
)

MAIN_MENU = [
    "1. Add Equipment",
    "2. Update Equipment",
    "3. Delete Equipment",
    "4. View",
    "5. Generate Report",
    "0. Exit",
]

VIEW_MENU = [
    "1. View One Equipment",
    "2. View All Equipment",
    "3. Filter Equipment",
    "4. Statistics",
    "0. Back",
]

CRITERION_MENU = [
    "1. Filter by Category",
    "2. Filter by Brand",
    "3. Filter by Location",
    "4. Filter by Status",
    "5. Filter by Hostname (contains)",
]

FILTER_MENU = CRITERION_MENU + ["0. Back"]


class Application:
    """Menu driven front end of the inventory system."""

    def __init__(self, base_dir=None, input_fn=None, out=None, seed: int = 0):
        self.db_base_dir = base_dir
        self.input_fn = input_fn
        self.out = out if out is not None else print
        self.seed = max(0, int(seed))
        self.db: InventoryDatabase | None = None
        self.service: InventoryService | None = None

    def line(self, text: str = "") -> None:
        self.out(text)

    def banner(self, title: str) -> None:
        self.line(rule("=", 40))
        self.line(f" {title}")
        self.line(rule("=", 40))
        self.line()

    def run(self) -> int:
        """Run the whole application; returns a process exit code."""
        try:
            self.startup()
        except CorruptFileError as error:
            self.line(str(error))
            self.discard_database()
            return 2
        except StorageError as error:
            self.line(f"ERROR: {error}")
            self.discard_database()
            return 2
        try:
            while True:
                choice = self.main_menu()
                if choice == "1":
                    self.safe(self.action_add_equipment)
                elif choice == "2":
                    self.safe(self.action_update_equipment)
                elif choice == "3":
                    self.safe(self.action_delete_equipment)
                elif choice == "4":
                    if not self.safe(self.view_menu):
                        self.line("  Returning to the main menu.")
                elif choice == "5":
                    self.safe(self.action_generate_report)
                else:
                    self.shutdown()
                    return 0
        except (EOFError, KeyboardInterrupt):
            self.line()
            self.line("Input closed. Shutting down safely...")
            self.shutdown()
            return 0
        except ValidationError as error:
            self.line()
            self.line(f"  [!] {error}")
            self.shutdown()
            return 0

    def discard_database(self) -> None:
        """Close whatever could be opened when startup failed."""
        if self.db is not None:
            self.db.close()
            self.db = None
            self.service = None

    def safe(self, action) -> bool:
        """Run a menu action, report any expected error, return success."""
        try:
            action()
            return True
        except (ValidationError, NotFoundError, DuplicateError) as error:
            self.line(f"  [!] {error}")
            return False
        except StorageError as error:
            self.line(f"  [!] Storage error: {error}")
            return False

    def startup(self) -> None:
        """Open the database, initialise missing files and show the banner."""
        self.db = InventoryDatabase(self.db_base_dir).open()
        self.service = InventoryService(self.db)
        self.banner(config.APP_NAME)
        if self.db.created_files:
            self.line("  Created new data files: " + ", ".join(sorted(self.db.created_files)))
        if self.seed:
            created = self.service.seed_demo_equipment(self.seed)
            self.line(f"  Seeded {len(created)} demo equipment record(s).")
        for line in self.db.status_lines():
            self.line("  " + line)
        self.line(
            f"  Index entries: {len(self.db.index)}   "
            f"Categories: {len(self.db.categories)}   "
            f"Free slots: {self.db.equipment_file.free_count}"
        )
        problems = self.db.index_problems()
        if problems:
            self.line("  [!] Index integrity problems detected:")
            for problem in problems[:5]:
                self.line(f"      - {problem}")
        else:
            self.line("  Integrity check: headers valid, index matches equipment.dat")
        self.line()

    def main_menu(self) -> str:
        """Show the main menu and return a validated choice."""
        self.banner(config.APP_NAME)
        for item in MAIN_MENU:
            self.line(f"  {item}")
        self.line()
        return read_choice("  Select: ", [item[0] for item in MAIN_MENU], self.input_fn)

    def view_menu(self) -> str:
        """Show the view submenu and dispatch until the user goes back."""
        while True:
            self.line()
            self.banner("View")
            for item in VIEW_MENU:
                self.line(f"  {item}")
            self.line()
            choice = read_choice(
                "  Select: ", [item[0] for item in VIEW_MENU], self.input_fn
            )
            if choice == "0":
                return choice
            if choice == "1":
                self.safe(self.action_view_one)
            elif choice == "2":
                self.safe(self.action_view_all)
            elif choice == "3":
                self.safe(self.filter_menu)
            else:
                self.safe(self.action_statistics)

    def filter_menu(self) -> None:
        """Collect one or more filter criteria and show matching equipment."""
        self.line()
        self.banner("Filter Equipment")
        for item in FILTER_MENU:
            self.line(f"  {item}")
        self.line()
        choice = read_choice(
            "  Select: ", [item[0] for item in FILTER_MENU], self.input_fn
        )
        if choice == "0":
            return
        criteria = self.read_filter_criteria(choice)
        while read_yes_no("  Add another filter? (y/n): ", self.input_fn):
            self.line()
            for item in CRITERION_MENU:
                self.line(f"  {item}")
            self.line()
            extra_choice = read_choice(
                "  Select: ", [item[0] for item in CRITERION_MENU], self.input_fn
            )
            criteria.update(self.read_filter_criteria(extra_choice))
        self.line()
        self.show_results(self.service.filter_equipment(**criteria), criteria)

    def read_filter_criteria(self, choice) -> dict:
        """Turn a filter menu choice into a keyword argument for the service."""
        if choice == "1":
            self.show_categories()
            return {
                "category_id": read_int(
                    "  Category ID: ",
                    self.input_fn,
                    minimum=config.CATEGORY_ID_MIN,
                    maximum=config.CATEGORY_ID_MAX,
                )
            }
        if choice == "2":
            return {
                "brand": read_non_empty(
                    "  Brand contains: ", self.input_fn, config.FIELD_SIZES["brand"]
                )
            }
        if choice == "3":
            return {
                "location": read_non_empty(
                    "  Location contains: ",
                    self.input_fn,
                    config.FIELD_SIZES["location"],
                )
            }
        if choice == "4":
            self.show_status_options()
            return {
                "status": read_int(
                    "  Status code: ",
                    self.input_fn,
                    minimum=1,
                    maximum=max(config.STATUS_NAMES),
                )
            }
        return {
            "text": read_non_empty(
                "  Hostname contains: ", self.input_fn, config.FIELD_SIZES["hostname"]
            )
        }

    def read_new_equipment_id(self):
        """Ask for a new equipment id; 0 cancels, duplicates are rejected."""
        while True:
            equipment_id = read_int(
                "  Equipment ID : ",
                self.input_fn,
                minimum=0,
                maximum=config.ID_MAX,
                default=0,
            )
            if equipment_id == 0:
                self.line("  Add cancelled.")
                return None
            if self.service.equipment_exists(equipment_id):
                self.line(
                    f"  [!] Equipment id {equipment_id} already exists. "
                    "Choose another id."
                )
                continue
            return equipment_id

    def read_category_id(self, current: int = None):
        """Ask for a category id that must exist and be active."""
        while True:
            category_id = read_int(
                "  Category ID  : ",
                self.input_fn,
                minimum=config.CATEGORY_ID_MIN,
                maximum=config.CATEGORY_ID_MAX,
                default=current,
            )
            try:
                return validate_category_id(
                    category_id, self.service.category_ids(active_only=True)
                )
            except ValidationError as error:
                self.line(f"  [!] {error}")

    def show_categories(self) -> None:
        self.line("  Available categories:")
        for category in self.service.list_categories():
            self.line(
                f"    {pad(category.category_id, 4)} {pad(category.category_name, 18)} "
                f"{category.description}"
            )

    def show_status_options(self) -> None:
        self.line("  Status options:")
        for code in sorted(config.STATUS_NAMES):
            if code == config.STATUS_FREE:
                continue
            self.line(f"    {code} = {config.status_name(code)}")

    def action_add_equipment(self) -> None:
        self.line()
        self.banner("Add Equipment")
        self.show_categories()
        self.show_status_options()
        self.line("  (enter 0 as the equipment id to cancel)")
        equipment_id = self.read_new_equipment_id()
        if equipment_id is None:
            return
        category_id = self.read_category_id()
        if category_id is None:
            return
        hostname = read_non_empty(
            "  Hostname     : ", self.input_fn, config.FIELD_SIZES["hostname"]
        )
        brand = read_non_empty(
            "  Brand        : ", self.input_fn, config.FIELD_SIZES["brand"]
        )
        model = read_non_empty(
            "  Model        : ", self.input_fn, config.FIELD_SIZES["model"]
        )
        serial_no = read_non_empty(
            "  Serial No    : ", self.input_fn, config.FIELD_SIZES["serial_no"]
        )
        location = read_non_empty(
            "  Location     : ", self.input_fn, config.FIELD_SIZES["location"]
        )
        status = read_int(
            "  Status       : ",
            self.input_fn,
            minimum=1,
            maximum=max(config.STATUS_NAMES),
            default=config.STATUS_ACTIVE,
        )
        price = read_float(
            "  Price        : ",
            self.input_fn,
            minimum=config.PRICE_MIN,
            maximum=config.PRICE_MAX,
            default=0.0,
        )
        free_before = self.db.equipment_file.free_count
        equipment, slot = self.service.add_equipment(
            equipment_id=equipment_id,
            category_id=category_id,
            hostname=hostname,
            brand=brand,
            model=model,
            serial_no=serial_no,
            location=location,
            status=status,
            price=price,
        )
        self.line()
        self.line("  [OK] Equipment added.")
        for line in equipment.detail_lines(
            self.service.category_name(equipment.category_id)
        ):
            self.line("  " + line)
        origin = "reused free slot" if free_before else "newly appended slot"
        self.line(
            f"  Stored in record slot {slot} "
            f"({origin}, offset {self.db.equipment_file.offset_of(slot)})."
        )

    def action_update_equipment(self) -> None:
        self.line()
        self.banner("Update Equipment")
        equipment_id = self.read_existing_id()
        if equipment_id is None:
            return
        current = self.service.get_equipment(equipment_id, log_view=False)
        self.line("  Current values (press Enter to keep a field unchanged):")
        for line in current.detail_lines(
            self.service.category_name(current.category_id)
        ):
            self.line("  " + line)
        self.line()
        self.show_categories()
        self.show_status_options()
        changes = {}
        category_id = self.read_category_id(current=current.category_id)
        if category_id != current.category_id:
            changes["category_id"] = category_id
        for field, prompt, limit in (
            ("hostname", "  New Hostname     : ", config.FIELD_SIZES["hostname"]),
            ("brand", "  New Brand        : ", config.FIELD_SIZES["brand"]),
            ("model", "  New Model        : ", config.FIELD_SIZES["model"]),
            ("serial_no", "  New Serial No    : ", config.FIELD_SIZES["serial_no"]),
            ("location", "  New Location     : ", config.FIELD_SIZES["location"]),
        ):
            value = read_optional(prompt, getattr(current, field), self.input_fn, limit)
            if value != getattr(current, field):
                changes[field] = value
        status = read_int(
            "  New Status       : ",
            self.input_fn,
            minimum=1,
            maximum=max(config.STATUS_NAMES),
            default=current.status,
        )
        if status != current.status:
            changes["status"] = status
        price = read_float(
            "  New Price        : ",
            self.input_fn,
            minimum=config.PRICE_MIN,
            maximum=config.PRICE_MAX,
            default=current.price,
        )
        if price != current.price:
            changes["price"] = price
        if not changes:
            self.line("  [i] Nothing changed.")
            return
        updated = self.service.update_equipment(current.equipment_id, **changes)
        self.line()
        self.line("  [OK] Equipment updated.")
        for line in updated.detail_lines(
            self.service.category_name(updated.category_id)
        ):
            self.line("  " + line)

    def action_delete_equipment(self) -> None:
        self.line()
        self.banner("Delete Equipment")
        equipment_id = self.read_existing_id()
        if equipment_id is None:
            return
        equipment = self.service.get_equipment(equipment_id, log_view=False)
        for line in equipment.detail_lines(
            self.service.category_name(equipment.category_id)
        ):
            self.line("  " + line)
        self.line()
        confirmed = read_yes_no(
            f"  Are you sure you want to delete equipment "
            f"{equipment.equipment_id}? (y/n): ",
            self.input_fn,
        )
        if not confirmed:
            self.line("  Delete cancelled.")
            return
        slot = self.db.index.get(equipment.equipment_id)
        self.service.delete_equipment(equipment.equipment_id)
        self.line(f"  [OK] Equipment {equipment.equipment_id} deleted.")
        self.line(
            f"  Record slot {slot} stays in the file as a free slot "
            f"and will be reused by the next add."
        )

    def action_view_one(self) -> None:
        self.line()
        self.banner("View One Equipment")
        equipment_id = read_int(
            "  Equipment ID: ",
            self.input_fn,
            minimum=config.ID_MIN,
            maximum=config.ID_MAX,
        )
        equipment = self.service.get_equipment(equipment_id)
        if equipment is None:
            self.line(f"  [i] No active equipment found with id {equipment_id}.")
            return
        self.line()
        self.line(rule("-", 40))
        for line in equipment.detail_lines(
            self.service.category_name(equipment.category_id)
        ):
            self.line(line)
        self.line(rule("-", 40))
        self.line(f"  (This view was recorded in {config.MOVEMENT_FILE_NAME}.)")

    def action_view_all(self) -> None:
        self.line()
        self.banner("View All Equipment")
        rows = self.service.view_all()
        if not rows:
            self.line("  [i] There is no equipment in the database yet.")
            return
        total = len(rows)
        start = 0
        while start < total:
            end = min(start + config.PAGE_SIZE, total)
            self.line()
            self.line("  " + Equipment.table_header())
            for equipment in rows[start:end]:
                self.line(
                    "  "
                    + equipment.table_row(
                        self.service.category_name(equipment.category_id)
                    )
                )
            self.line()
            self.line(f"  Showing {start + 1}-{end} of {total} active record(s).")
            start = end
            if start >= total:
                break
            answer = read_line(
                f"  Press Enter for the next page, q to stop: ", self.input_fn
            ).lower()
            if answer in ("q", "quit", "stop"):
                self.line(f"  Stopped at record {end} of {total}.")
                break

    def show_results(self, rows, criteria) -> None:
        if criteria:
            described = ", ".join(f"{key}={value}" for key, value in criteria.items())
            self.line(f"  Filter: {described}")
        if not rows:
            self.line("  [i] No equipment matches the filter.")
            return
        self.line()
        self.line("  " + Equipment.table_header())
        for equipment in rows:
            self.line(
                "  "
                + equipment.table_row(
                    self.service.category_name(equipment.category_id)
                )
            )
        self.line()
        self.line(f"  {len(rows)} record(s) shown.")

    def action_statistics(self) -> None:
        self.line()
        self.banner("Statistics")
        for line in self.statistics_lines(self.service.statistics()):
            self.line(line)

    def statistics_lines(self, stats) -> list[str]:
        lines = [
            rule("-", 40),
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
            rule("-", 40),
            "Equipment by category:",
        ]
        for category in self.service.list_categories(active_only=False):
            lines.append(
                f"  {pad(category.category_name, 20)}: "
                f"{stats['by_category'].get(category.category_id, 0)}"
            )
        lines.append(rule("-", 40))
        lines.append("Equipment by location:")
        for location, count in sorted(
            stats["by_location"].items(), key=lambda item: (-item[1], item[0])
        )[:10]:
            lines.append(f"  {pad(location or '(unknown)', 25)}: {count}")
        lines.append(rule("-", 40))
        return lines

    def action_generate_report(self) -> None:
        self.line()
        self.banner("Generate Report")
        path = report_module.generate_report(self.service)
        self.line(f"  [OK] Report written to {path}")
        self.line()
        for line in report_module.build_report_lines(self.service)[:18]:
            self.line("  " + line)

    def read_existing_id(self):
        equipment_id = read_int(
            "  Equipment ID : ",
            self.input_fn,
            minimum=config.ID_MIN,
            maximum=config.ID_MAX,
        )
        if not self.service.equipment_exists(equipment_id):
            self.line(f"  [!] Equipment {equipment_id} does not exist.")
            return None
        return equipment_id

    def shutdown(self) -> None:
        """Flush pending writes, update headers, sync and close the files."""
        if self.db is None:
            return
        try:
            self.db.close()
            self.line()
            self.line("  All data flushed and closed safely. Goodbye!")
        finally:
            self.db = None
            self.service = None


def configure_console() -> None:
    """Make terminal output safe for non ASCII paths and user names."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        for arguments in ({"encoding": "utf-8", "errors": "replace"},
                          {"errors": "replace"}):
            try:
                reconfigure(**arguments)
                break
            except (ValueError, OSError, LookupError):
                continue


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=f"{config.APP_NAME} (binary file I/O demo)"
    )
    parser.add_argument(
        "--base-dir",
        default=None,
        help="directory holding the data/ folder and report.txt "
             f"(default: {config.BASE_DIR})",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        metavar="N",
        help="create N demo equipment records before showing the menu",
    )
    return parser


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)
    configure_console()
    return Application(base_dir=args.base_dir, seed=args.seed).run()


if __name__ == "__main__":
    sys.exit(main())

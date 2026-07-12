import sqlite3
from pathlib import Path


DB_PATH = Path(__file__).resolve().parent / "truckgrad.db"


def fix_mojibake(value: str | None) -> str | None:
    if not value:
        return value
    if not any(marker in value for marker in ("Ð", "Ñ", "Р")):
        return value
    try:
        fixed = value.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value
    return fixed if fixed else value


def main() -> None:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")

    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    rows = cursor.execute(
        "SELECT id, name, description FROM products"
    ).fetchall()

    updated_rows = 0

    for product_id, name, description in rows:
        fixed_name = fix_mojibake(name)
        fixed_description = fix_mojibake(description)

        if fixed_name == name and fixed_description == description:
            continue

        cursor.execute(
            "UPDATE products SET name = ?, description = ? WHERE id = ?",
            (fixed_name, fixed_description, product_id),
        )
        updated_rows += 1

    connection.commit()
    connection.close()

    print(f"Processed: {len(rows)}")
    print(f"Updated: {updated_rows}")


if __name__ == "__main__":
    main()
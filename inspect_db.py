import sqlite3
from pathlib import Path

FILES = [
    Path("data/stock_scout.db"),
    Path("data/stock_scout_local_backup.db"),
]

for path in FILES:
    print("\n" + "=" * 55)
    print("DATABASE:", path)
    print("=" * 55)

    if not path.exists():
        print("File non trovato")
        continue

    uri = f"file:{path.resolve().as_posix()}?mode=ro"

    with sqlite3.connect(uri, uri=True) as con:
        con.row_factory = sqlite3.Row

        tables = [
            r["name"]
            for r in con.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' ORDER BY name"
            )
        ]

        print("Tabelle:", tables)

        for table in tables:
            count = con.execute(
                f'SELECT COUNT(*) FROM "{table}"'
            ).fetchone()[0]
            print(f"{table}: {count} righe")

        for table in ("positions", "trades", "portfolio_state"):
            if table not in tables:
                continue

            columns = [
                r["name"]
                for r in con.execute(
                    f'PRAGMA table_info("{table}")'
                )
            ]

            print(f"\n--- {table} ---")
            print("Colonne:", columns)

            if table == "positions" and "ticker" in columns:
                rows = con.execute(
                    'SELECT * FROM positions '
                    'WHERE ticker = ? ORDER BY id DESC LIMIT 5',
                    ("WST",)
                ).fetchall()

            elif table == "trades" and "ticker" in columns:
                rows = con.execute(
                    'SELECT * FROM trades '
                    'WHERE ticker = ? ORDER BY id DESC LIMIT 5',
                    ("WST",)
                ).fetchall()

            else:
                rows = con.execute(
                    f'SELECT * FROM "{table}" LIMIT 5'
                ).fetchall()

            for row in rows:
                data = dict(row)

                if "signal_snapshot" in data:
                    value = data["signal_snapshot"]
                    data["signal_snapshot"] = (
                        str(value)[:250] + "..."
                        if value and len(str(value)) > 250
                        else value
                    )

                print(data)
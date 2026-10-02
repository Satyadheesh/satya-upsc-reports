"""Apply schema.sql to the UPSC DB (idempotent)."""
import pathlib
import re

from common.db import close_all, upsc_db


def main():
    sql = pathlib.Path(__file__).with_name("schema.sql").read_text()
    sql = re.sub(r"--[^\n]*", "", sql)
    stmts = [s.strip() for s in sql.split(";") if s.strip()]
    c = upsc_db()
    c.batch(stmts)
    print(f"schema applied ({len(stmts)} statements)")


if __name__ == "__main__":
    try:
        main()
    finally:
        close_all()

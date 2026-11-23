"""Create the databases parallel test processes use (see _test_database in conftest.py).

    uv run python tests/make_test_databases.py 4

Each is an empty copy of gobernar360_test owned by the owner role; the test session
migrates it. Existing ones are replaced.
"""

import sys

import psycopg

count = int(sys.argv[1]) if len(sys.argv) > 1 else 4
with psycopg.connect(
    "postgresql://gobernar360:gobernar360@localhost:5434/gobernar360", autocommit=True
) as connection:
    for index in range(count):
        name = f"gobernar360_test_{index}"
        connection.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        connection.execute(f'CREATE DATABASE "{name}" OWNER gobernar360')
        print(f"created {name}")

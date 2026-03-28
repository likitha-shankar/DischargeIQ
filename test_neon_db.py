"""
DIS-1 smoke test: verify Neon PostgreSQL connectivity.

Connects to the Neon database, creates the discharge_history table if it
does not exist, and verifies the table is accessible.

Run:  source .venv/bin/activate && python test_neon_db.py
Requires: DATABASE_URL set in .env or environment.
"""

import asyncio
import os
import sys

from dotenv import load_dotenv
import asyncpg

load_dotenv()


async def test_neon_connection():
    """
    Connect to Neon PostgreSQL, create the discharge_history table, and verify it exists.

    Raises:
        asyncpg.PostgresError: If the connection or query fails.
        AssertionError: If the table does not exist after creation.
    """
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL is not set. Add it to .env and try again.")
        sys.exit(1)

    conn = None
    try:
        conn = await asyncpg.connect(database_url)

        version = await conn.fetchval("SELECT version()")
        print(f"Connected to: {version}")

        # Create the table using the same schema as db/schema.sql
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS discharge_history (
                id SERIAL PRIMARY KEY,
                session_id VARCHAR(64) NOT NULL,
                document_hash VARCHAR(64) NOT NULL,
                primary_diagnosis VARCHAR(255),
                discharge_date VARCHAR(50),
                pipeline_status VARCHAR(20),
                extracted_fields JSONB,
                fk_scores JSONB,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        print("Table discharge_history: OK")

        # Verify the table actually exists
        exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'discharge_history'
            )
        """)
        assert exists, "Table was not created"
        print("Neon DB test PASSED")

    except asyncpg.InvalidPasswordError as auth_error:
        print(f"Database authentication failed — check DATABASE_URL credentials: {auth_error}")
        sys.exit(1)
    except OSError as net_error:
        print(f"Could not reach the database server: {net_error}")
        sys.exit(1)
    finally:
        if conn:
            await conn.close()


if __name__ == "__main__":
    asyncio.run(test_neon_connection())

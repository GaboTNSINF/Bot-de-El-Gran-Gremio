import asyncio
import aiosqlite
import os

DB_PATH = "test.db"

async def main():
    conn = await aiosqlite.connect(DB_PATH)
    await conn.execute("CREATE TABLE IF NOT EXISTS test (id INTEGER PRIMARY KEY, name TEXT)")
    await conn.execute("INSERT INTO test (id, name) VALUES (1, 'bolt')")
    await conn.commit()

    async with conn.execute("DELETE FROM test WHERE id = ?", (1,)) as cursor:
        print("deleted existing:", cursor.rowcount > 0)

    async with conn.execute("DELETE FROM test WHERE id = ?", (2,)) as cursor:
        print("deleted non-existing:", cursor.rowcount > 0)

    await conn.commit()
    await conn.close()

    os.remove(DB_PATH)

asyncio.run(main())

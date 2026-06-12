import asyncio
import database
import os

async def main():
    if os.path.exists("gremio.db"):
        os.remove("gremio.db")

    await database.init_db()

    # Comprobar que el puente también migró los 20,000,000 a la tabla V3 (economia_billetera)
    async with database.get_db() as db:
        async with db.execute("SELECT balance_pc FROM economia_billetera WHERE user_id = 0") as cursor:
            row = await cursor.fetchone()
            assert row["balance_pc"] == 20000000, f"Expected 20M in V3, got {row['balance_pc']}"


    print("Test passed: Bóveda inicializada correctamente en 20 millones.")

asyncio.run(main())

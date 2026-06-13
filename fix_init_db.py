import re

with open('database.py', 'r') as f:
    content = f.read()

match1 = re.search(r'async def registrar_personaje\(.*?\)\s*->\s*bool:\n.*?except aiosqlite\.IntegrityError as e:\n.*?return False\n.*?raise\n.*?except Exception:\n\s*raise', content, flags=re.DOTALL)
if match1:
    registrar_new = """async def registrar_personaje(user_id: int, name: str, race: str, char_class: str, age: int, height: str, link: str) -> bool:
    try:
        async with get_db() as db:
            async with transaccion_gremial(db):
                await db.execute('''
                    INSERT INTO aventureros (user_id, char_name, char_race, char_class, char_age, char_height, sheet_link, nivel, sesiones_jugadas)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1, 0)
                ''', (user_id, name, race, char_class, age, height, link))
        return True
    except TransactionLogicError:
        return False
    except aiosqlite.IntegrityError as e:
        error_msg = str(e).lower()
        if "aventureros.user_id" in error_msg and ("unique" in error_msg or "primary key" in error_msg):
            return False
        raise
    except Exception:
        raise"""
    content = content[:match1.start()] + registrar_new + content[match1.end():]

# In init_db, replace the UPDATE inventario_materiales block:
old_update = """                await db.execute('''
                    UPDATE inventario_materiales
                    SET cantidad = (
                        SELECT SUM(cantidad) FROM inventarios
                        WHERE user_id = inventario_materiales.user_id
                          AND REPLACE(LOWER(producto_nombre), ' ', '_') = inventario_materiales.item_id
                    )
                    WHERE (user_id, item_id) IN (
                        SELECT user_id, REPLACE(LOWER(producto_nombre), ' ', '_') FROM inventarios
                    );
                ''')"""

new_update = """                await db.execute('''
                    CREATE TEMPORARY TABLE temp_inventarios_migracion AS
                    SELECT user_id,
                           REPLACE(LOWER(producto_nombre), ' ', '_') as item_id,
                           SUM(cantidad) as total_acumulado
                    FROM inventarios
                    GROUP BY user_id, REPLACE(LOWER(producto_nombre), ' ', '_')
                ''')

                await db.execute("CREATE INDEX idx_temp_inventarios ON temp_inventarios_migracion(user_id, item_id);")

                await db.execute('''
                    INSERT OR IGNORE INTO inventario_materiales (user_id, item_id, cantidad)
                    SELECT user_id, item_id, 0
                    FROM temp_inventarios_migracion;
                ''')

                await db.execute('''
                    UPDATE inventario_materiales
                    SET cantidad = (
                        SELECT total_acumulado FROM temp_inventarios_migracion
                        WHERE temp_inventarios_migracion.user_id = inventario_materiales.user_id
                          AND temp_inventarios_migracion.item_id = inventario_materiales.item_id
                    )
                    WHERE (user_id, item_id) IN (SELECT user_id, item_id FROM temp_inventarios_migracion);
                ''')

                await db.execute("DROP TABLE temp_inventarios_migracion")"""

content = content.replace(old_update, new_update)

with open('database.py', 'w') as f:
    f.write(content)

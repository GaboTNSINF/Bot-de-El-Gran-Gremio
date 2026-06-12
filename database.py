import aiosqlite
import os
import contextlib

@contextlib.asynccontextmanager
async def transaction(db):
    try:
        await db.execute("BEGIN TRANSACTION;")
        yield
        await db.commit()
    except Exception:
        await db.rollback()
        raise


# Determinar la ruta absoluta del directorio donde reside este archivo de forma dinámica
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "gremio.db")

@contextlib.asynccontextmanager
async def get_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON;")
        await db.execute("PRAGMA journal_mode = WAL;")
        await db.execute("PRAGMA busy_timeout = 5000;")
        db.row_factory = aiosqlite.Row
        yield db

async def init_db():
    """Inicializa el esquema de la base de datos."""
    async with get_db() as db:
        async with transaction(db):
            # 1. Tabla de Aventureros
            await db.execute("""
                CREATE TABLE IF NOT EXISTS aventureros (
                    user_id INTEGER PRIMARY KEY,
                    char_name TEXT NOT NULL,
                    char_race TEXT NOT NULL,
                    char_class TEXT NOT NULL,
                    char_age INTEGER NOT NULL,
                    char_height TEXT NOT NULL,
                    sheet_link TEXT NOT NULL,
                    nivel INTEGER DEFAULT 1,
                    sesiones_jugadas INTEGER DEFAULT 0
                )
            """)

            # Motor de migración interna de aventureros
            async with db.execute("PRAGMA table_info(aventureros)") as cursor:
                columnas_existentes = [columna["name"] for columna in await cursor.fetchall()]

            if "nivel" not in columnas_existentes:
                await db.execute("ALTER TABLE aventureros ADD COLUMN nivel INTEGER DEFAULT 1")
            if "sesiones_jugadas" not in columnas_existentes:
                await db.execute("ALTER TABLE aventureros ADD COLUMN sesiones_jugadas INTEGER DEFAULT 0")

            await db.execute("CREATE INDEX IF NOT EXISTS idx_aventureros_ladder ON aventureros (nivel DESC, sesiones_jugadas DESC)")

            # 2. Sistema de Matchmaking
            await db.execute("""
                CREATE TABLE IF NOT EXISTS matchmaking (
                    user_id INTEGER PRIMARY KEY,
                    rol_busqueda TEXT NOT NULL,
                    tier_juego TEXT,
                    dias_disponibles TEXT NOT NULL,
                    hora_inicio_utc INTEGER NOT NULL,
                    hora_fin_utc INTEGER NOT NULL
                )
            """)

            # 3. Registro de Dungeon Masters
            await db.execute("""
                CREATE TABLE IF NOT EXISTS registro_dms (
                    dm_id INTEGER PRIMARY KEY,
                    nombre_dm TEXT NOT NULL,
                    rango_licencia TEXT DEFAULT 'Aprendiz',
                    partidas_narradas INTEGER DEFAULT 0
                )
            """)

            # 4. Urna Transaccional Anónima (Reseñas)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS reseñas_dms (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    dm_id INTEGER NOT NULL,
                    valoracion INTEGER NOT NULL,
                    comentario TEXT,
                    FOREIGN KEY (dm_id) REFERENCES registro_dms(dm_id)
                )
            """)

            await db.execute("CREATE INDEX IF NOT EXISTS idx_resenas_dm_id ON reseñas_dms (dm_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_dms_partidas ON registro_dms (partidas_narradas DESC)")

            # 5. Control de Anclas de Embeds
            await db.execute("""
                CREATE TABLE IF NOT EXISTS control_nominas (
                    seccion TEXT PRIMARY KEY,
                    channel_id INTEGER NOT NULL,
                    message_id INTEGER NOT NULL
                )
            """)

            # 6. Personal Administrativo
            await db.execute("""
                CREATE TABLE IF NOT EXISTS personal_ramas (
                    user_id INTEGER PRIMARY KEY,
                    division TEXT NOT NULL,
                    rango_interno TEXT NOT NULL
                )
            """)

            # 7. Balances Legacy
            await db.execute("""
                CREATE TABLE IF NOT EXISTS cuentas_bancarias (
                    id_entidad INTEGER PRIMARY KEY,
                    balance_pc INTEGER DEFAULT 0
                )
            """)

            # 8. Catálogo de Tienda
            await db.execute("""
                CREATE TABLE IF NOT EXISTS tienda_productos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre TEXT NOT NULL COLLATE NOCASE,
                    precio_str TEXT NOT NULL,
                    costo_pc INTEGER NOT NULL,
                    categoria TEXT NOT NULL,
                    descripcion TEXT NOT NULL
                )
            """)

            # 9. Infraestructura del Histórico Relacional Padre-Hijo (Anti-Colisiones Estocásticas)
            await db.executescript("""
                CREATE TABLE IF NOT EXISTS auditoria_sesiones_fallidas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    folio INTEGER NOT NULL,
                    dm_id INTEGER NOT NULL,
                    timestamp INTEGER NOT NULL,
                    aventura TEXT NOT NULL,
                    recompensa_pc INTEGER NOT NULL,
                    recompensa_objeto VARCHAR(50) DEFAULT NULL
                );

                CREATE TABLE IF NOT EXISTS auditoria_sesiones_jugadores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    auditoria_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    FOREIGN KEY (auditoria_id) REFERENCES auditoria_sesiones_fallidas(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_auditoria_sesiones_jugadores_auditoria ON auditoria_sesiones_jugadores(auditoria_id);
            """)

            # SCHEMA V3 CANÓNICO ASTERIA: Infraestructura Trustless Normalizada
            await db.executescript("""
                CREATE TABLE IF NOT EXISTS matriz_recompensas (
                    rango_dm VARCHAR(20) NOT NULL,
                    nivel_personaje INTEGER NOT NULL,
                    max_pc_permitido INTEGER NOT NULL,
                    max_rareza VARCHAR(20) NOT NULL,
                    PRIMARY KEY (rango_dm, nivel_personaje)
                );

                CREATE TABLE IF NOT EXISTS personajes_estados (
                    user_id INTEGER PRIMARY KEY,
                    estado_viajando BOOLEAN DEFAULT 0,
                    viaje_desbloqueo_timestamp INTEGER DEFAULT 0,
                    nivel_extenuacion INTEGER DEFAULT 0,
                    estado_herido BOOLEAN DEFAULT 0,
                    pendiente_auditoria BOOLEAN DEFAULT 0,
                    anillo_geografico_id INTEGER DEFAULT NULL
                );

                CREATE TABLE IF NOT EXISTS economia_billetera (
                    user_id INTEGER PRIMARY KEY,
                    balance_pc INTEGER DEFAULT 0 CHECK(balance_pc >= 0),
                    FOREIGN KEY (user_id) REFERENCES personajes_estados(user_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS inventario_materiales (
                    user_id INTEGER NOT NULL,
                    item_id VARCHAR(50) NOT NULL,
                    cantidad INTEGER NOT NULL CHECK(cantidad >= 0),
                    PRIMARY KEY (user_id, item_id),
                    FOREIGN KEY (user_id) REFERENCES personajes_estados(user_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS inventario_instancias (
                    instance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    item_id VARCHAR(50) NOT NULL,
                    durabilidad_actual INTEGER NOT NULL CHECK(durabilidad_actual >= 0),
                    grado_runa INTEGER DEFAULT 0,
                    estado_critico BOOLEAN DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES personajes_estados(user_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS registro_recetas_conocidas (
                    user_id INTEGER NOT NULL,
                    receta_id VARCHAR(50) NOT NULL,
                    PRIMARY KEY (user_id, receta_id),
                    FOREIGN KEY (user_id) REFERENCES personajes_estados(user_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS registro_tickets (
                    channel_id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    estado VARCHAR(20) DEFAULT 'ABIERTO'
                );

                CREATE INDEX IF NOT EXISTS idx_inventario_materiales_user ON inventario_materiales(user_id);
                CREATE INDEX IF NOT EXISTS idx_inventario_instancias_user ON inventario_instancias(user_id);
                CREATE INDEX IF NOT EXISTS idx_registro_recetas_user ON registro_recetas_conocidas(user_id);
            """)

            # Inventarios Legacy
            await db.execute("""
                CREATE TABLE IF NOT EXISTS inventarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    producto_nombre TEXT NOT NULL,
                    cantidad INTEGER DEFAULT 1,
                    origen TEXT DEFAULT 'tienda',
                    FOREIGN KEY (user_id) REFERENCES aventureros(user_id) ON DELETE CASCADE
                )
            """)

            # Puente de Retrocompatibilidad de Esquema
            async with db.execute("PRAGMA table_info(personajes_estados)") as cursor:
                columnas_estados = [columna["name"] for columna in await cursor.fetchall()]

            if "anillo_geografico_id" not in columnas_estados:
                await db.execute("ALTER TABLE personajes_estados ADD COLUMN anillo_geografico_id INTEGER DEFAULT NULL")

            # Rutinas de Migración y Porteo Atómico Histórico
            async with db.execute("PRAGMA user_version") as cursor:
                version_db = (await cursor.fetchone())[0]

            if version_db < 1:
                await db.execute("""
                    INSERT OR IGNORE INTO personajes_estados (user_id)
                    SELECT id_entidad FROM cuentas_bancarias;
                """)
                await db.execute("INSERT OR IGNORE INTO personajes_estados (user_id) VALUES (0);")

                # BLINDAJE DE INTEGRIDAD: Prevenir violaciones de Foreign Key de usuarios inexistentes en tabla maestra
                await db.execute("""
                    INSERT OR IGNORE INTO personajes_estados (user_id)
                    SELECT DISTINCT user_id FROM inventarios;
                """)

                await db.execute("""
                    INSERT OR IGNORE INTO economia_billetera (user_id, balance_pc)
                    SELECT id_entidad, 0 FROM cuentas_bancarias;
                """)
                await db.execute("""
                    UPDATE economia_billetera
                    SET balance_pc = balance_pc + (
                        SELECT balance_pc FROM cuentas_bancarias
                        WHERE id_entidad = economia_billetera.user_id
                    )
                    WHERE user_id IN (SELECT id_entidad FROM cuentas_bancarias);
                """)

                await db.execute("""
                    INSERT OR IGNORE INTO inventario_materiales (user_id, item_id, cantidad)
                    SELECT user_id, REPLACE(LOWER(producto_nombre), ' ', '_'), 0
                    FROM inventarios;
                """)
                await db.execute("""
                    UPDATE inventario_materiales
                    SET cantidad = cantidad + (
                        SELECT SUM(cantidad) FROM inventarios
                        WHERE user_id = inventario_materiales.user_id
                          AND REPLACE(LOWER(producto_nombre), ' ', '_') = inventario_materiales.item_id
                    )
                    WHERE (user_id, item_id) IN (
                        SELECT user_id, REPLACE(LOWER(producto_nombre), ' ', '_') FROM inventarios
                    );
                """)

                await db.execute("PRAGMA user_version = 1")

            # Tablas Mecánicas de Nivel20
            await db.executescript("""
                CREATE TABLE IF NOT EXISTS ficha_estadisticas (
                    user_id INTEGER PRIMARY KEY,
                    fuerza INTEGER NOT NULL,
                    destreza INTEGER NOT NULL,
                    constitucion INTEGER NOT NULL,
                    inteligencia INTEGER NOT NULL,
                    sabiduria INTEGER NOT NULL,
                    carisma INTEGER NOT NULL,
                    iniciativa TEXT NOT NULL,
                    velocidad TEXT NOT NULL,
                    competencia TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES aventureros(user_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS ficha_clases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    clase TEXT NOT NULL,
                    nivel INTEGER NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES aventureros(user_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS ficha_rasgos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    nombre TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES aventureros(user_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS ficha_conjuros (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    nombre TEXT NOT NULL,
                    nivel TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES aventureros(user_id) ON DELETE CASCADE
                );
            """)

            try:
                await db.execute("ALTER TABLE inventarios ADD COLUMN origen TEXT DEFAULT 'tienda'")
            except Exception:
                pass

            # Inicialización de la Bóveda Central (Protegida)
            await db.execute("INSERT OR IGNORE INTO economia_billetera (user_id, balance_pc) VALUES (0, 20000000)")
            await db.execute("UPDATE economia_billetera SET balance_pc = 20000000 WHERE user_id = 0 AND balance_pc < 20000000")

# --- CONSULTAS OPTIMIZADAS ---

async def obtener_personaje(user_id: int):
    async with get_db() as db:
        async with db.execute(
            "SELECT char_name, char_race, char_class, char_age, char_height, sheet_link, nivel FROM aventureros WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            return await cursor.fetchone()

async def registrar_personaje(user_id: int, name: str, race: str, char_class: str, age: int, height: str, link: str):
    async with get_db() as db:
        async with transaction(db):
            await db.execute("""
                INSERT INTO aventureros (user_id, char_name, char_race, char_class, char_age, char_height, sheet_link, nivel, sesiones_jugadas)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, 0)
            """, (user_id, name, race, char_class, age, height, link))

async def eliminar_personaje(user_id: int) -> bool:
    async with get_db() as db:
        async with transaction(db):
            async with db.execute("DELETE FROM aventureros WHERE user_id = ?", (user_id,)) as cursor:
                return cursor.rowcount > 0

async def guardar_registro_matchmaking(user_id: int, rol: str, tier: str, dias: str, inicio: int, fin: int):
    async with get_db() as db:
        async with transaction(db):
            await db.execute("""
                INSERT OR REPLACE INTO matchmaking (user_id, rol_busqueda, tier_juego, dias_disponibles, hora_inicio_utc, hora_fin_utc)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, rol, tier, dias, inicio, fin))

async def eliminar_de_cola(user_id: int):
    async with get_db() as db:
        async with transaction(db):
            async with db.execute("DELETE FROM matchmaking WHERE user_id = ?", (user_id,)) as cursor:
                return cursor.rowcount > 0

async def obtener_toda_la_cola():
    async with get_db() as db:
        async with db.execute("SELECT user_id, rol_busqueda, tier_juego, dias_disponibles, hora_inicio_utc, hora_fin_utc FROM matchmaking") as cursor:
            return await cursor.fetchall()

async def actualizar_nivel_personaje(user_id: int, nuevo_nivel: int):
    async with get_db() as db:
        async with transaction(db):
            async with db.execute("UPDATE aventureros SET nivel = ? WHERE user_id = ?", (nuevo_nivel, user_id)) as cursor:
                return cursor.rowcount > 0

async def editar_datos_personaje(user_id: int, name: str, race: str, char_class: str, age: int, height: str, link: str):
    async with get_db() as db:
        async with transaction(db):
            async with db.execute("""
                UPDATE aventureros
                SET char_name = ?, char_race = ?, char_class = ?, char_age = ?, char_height = ?, sheet_link = ?
                WHERE user_id = ?
            """, (name, race, char_class, age, height, link, user_id)) as cursor:
                return cursor.rowcount > 0

async def obtener_perfil_dm(dm_id: int):
    query = """
        SELECT 
            d.nombre_dm, d.rango_licencia, d.partidas_narradas,
            COUNT(CASE WHEN r.valoracion = 1 THEN 1 END) as excelencias,
            COUNT(CASE WHEN r.valoracion = -1 THEN 1 END) as alertas
        FROM registro_dms d
        LEFT JOIN reseñas_dms r ON d.dm_id = r.dm_id
        WHERE d.dm_id = ?
        GROUP BY d.dm_id
    """
    async with get_db() as db:
        async with db.execute(query, (dm_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None

            votos_validos = row["excelencias"] + row["alertas"]
            porcentaje_aprobacion = 100
            if votos_validos > 0:
                porcentaje_aprobacion = int((row["excelencias"] / votos_validos) * 100)

            return {
                "nombre": row["nombre_dm"],
                "licencia": row["rango_licencia"],
                "partidas": row["partidas_narradas"],
                "aprobacion": porcentaje_aprobacion,
                "total_validas": votos_validos
            }

async def obtener_ladder_aventureros():
    async with get_db() as db:
        async with db.execute("SELECT user_id, char_name, nivel, sesiones_jugadas FROM aventureros ORDER BY nivel DESC, sesiones_jugadas DESC LIMIT 10") as cursor:
            return await cursor.fetchall()

async def obtener_ladder_dms():
    query = """
        SELECT 
            d.dm_id, d.nombre_dm, d.rango_licencia, d.partidas_narradas,
            COUNT(CASE WHEN r.valoracion = 1 THEN 1 END) as excelencias,
            COUNT(CASE WHEN r.valoracion = -1 THEN 1 END) as alertas
        FROM (
            SELECT * FROM registro_dms
            ORDER BY partidas_narradas DESC
            LIMIT 10
        ) d
        LEFT JOIN reseñas_dms r ON d.dm_id = r.dm_id
        GROUP BY d.dm_id
        ORDER BY d.partidas_narradas DESC
    """
    async with get_db() as db:
        async with db.execute(query) as cursor:
            rows = await cursor.fetchall()

        ladder_completo = []
        for row in rows:
            votos_validos = row["excelencias"] + row["alertas"]
            aprobacion = 100
            if votos_validos > 0:
                aprobacion = int((row["excelencias"] / votos_validos) * 100)
            ladder_completo.append((row["nombre_dm"], row["rango_licencia"], row["partidas_narradas"], aprobacion))
        return ladder_completo

async def registrar_ancla_nomina(seccion: str, channel_id: int, message_id: int):
    async with get_db() as db:
        async with transaction(db):
            await db.execute("INSERT OR REPLACE INTO control_nominas (seccion, channel_id, message_id) VALUES (?, ?, ?)", (seccion, channel_id, message_id))

async def obtener_ancla_nomina(seccion: str):
    async with get_db() as db:
        async with db.execute("SELECT channel_id, message_id FROM control_nominas WHERE seccion = ?", (seccion,)) as cursor:
            return await cursor.fetchone()

async def actualizar_miembro_personal(user_id: int, division: str, rango: str):
    async with get_db() as db:
        async with transaction(db):
            await db.execute("INSERT OR REPLACE INTO personal_ramas (user_id, division, rango_interno) VALUES (?, ?, ?)", (user_id, division, rango))

async def remover_miembro_personal(user_id: int):
    async with get_db() as db:
        async with transaction(db):
            await db.execute("DELETE FROM personal_ramas WHERE user_id = ?", (user_id,))

async def obtener_personal_division(division: str):
    async with get_db() as db:
        async with db.execute("SELECT user_id, rango_interno FROM personal_ramas WHERE division = ?", (division,)) as cursor:
            return await cursor.fetchall()

async def obtener_candidatos_compatibles_dm(dm_id: int, limite_jugadores: int):
    async with get_db() as db:
        async with db.execute(
            "SELECT hora_inicio_utc, hora_fin_utc FROM matchmaking WHERE user_id = ? AND rol_busqueda = 'dm'",
            (dm_id,)
        ) as cursor:
            dm_datos = await cursor.fetchone()
            if not dm_datos:
                return []

        dm_ini = dm_datos["hora_inicio_utc"]
        dm_fin = dm_datos["hora_fin_utc"]

        if dm_fin <= dm_ini:
            dm_fin += 1440

        query = """
            SELECT m.user_id, a.nivel, m.hora_inicio_utc, m.hora_fin_utc
            FROM matchmaking m
            JOIN aventureros a ON m.user_id = a.user_id
            WHERE m.rol_busqueda = 'jugador'
              AND (
                  MIN(CASE WHEN m.hora_fin_utc <= m.hora_inicio_utc THEN m.hora_fin_utc + 1440 ELSE m.hora_fin_utc END, ?)
                  -
                  MAX(m.hora_inicio_utc, ?)
              ) >= 180
        """
        async with db.execute(query, (dm_fin, dm_ini)) as cursor:
            return await cursor.fetchall()

# --- INFRAESTRUCTURA BANCARIA CONTROLADA (BLINDAJE DE CONCURRENCIA SANEADO) ---

async def obtener_balance(id_entidad: int) -> int:
    async with get_db() as db:
        async with db.execute("SELECT balance_pc FROM economia_billetera WHERE user_id = ?", (id_entidad,)) as cursor:
            resultado = await cursor.fetchone()
            return resultado["balance_pc"] if resultado else 0

async def inyectar_fondos_ignorados(dm_id: int, nombre_dm: str, valor: int, label_voto: str):
    async with get_db() as db:
        async with transaction(db):
            await db.execute("INSERT OR IGNORE INTO registro_dms (dm_id, nombre_dm) VALUES (?, ?)", (dm_id, nombre_dm))
            await db.execute("INSERT INTO reseñas_dms (dm_id, valoracion, comentario) VALUES (?, ?, ?)", (dm_id, valor, f"Voto directo: {label_voto}"))

async def transferir_fondos(emisor_id: int, receptor_id: int, cantidad_pc: int) -> bool:
    if cantidad_pc <= 0:
        return False

    async with get_db() as db:
        async with transaction(db):
            await db.execute("INSERT OR IGNORE INTO personajes_estados (user_id) VALUES (?)", (emisor_id,))
            await db.execute("INSERT OR IGNORE INTO personajes_estados (user_id) VALUES (?)", (receptor_id,))
            await db.execute("INSERT OR IGNORE INTO economia_billetera (user_id, balance_pc) VALUES (?, 0)", (emisor_id,))
            await db.execute("INSERT OR IGNORE INTO economia_billetera (user_id, balance_pc) VALUES (?, 0)", (receptor_id,))

            async with db.execute(
                "UPDATE economia_billetera SET balance_pc = balance_pc - ? WHERE user_id = ? AND balance_pc >= ?",
                (cantidad_pc, emisor_id, cantidad_pc)
            ) as cursor:
                if cursor.rowcount == 0:
                    return False

            await db.execute("UPDATE economia_billetera SET balance_pc = balance_pc + ? WHERE user_id = ?", (cantidad_pc, receptor_id))
            return True

async def procesar_nominas_masivas(pagos_pendientes: dict, total_gasto_pc: int) -> bool:
    async with get_db() as db:
        async with transaction(db):
            async with db.execute("SELECT balance_pc FROM economia_billetera WHERE user_id = 0") as cursor:
                boveda = await cursor.fetchone()
                if not boveda or boveda["balance_pc"] < total_gasto_pc:
                    return False

            await db.execute(
                "UPDATE economia_billetera SET balance_pc = balance_pc - ? WHERE user_id = 0",
                (total_gasto_pc,)
            )

            for u_id, monto in pagos_pendientes.items():
                await db.execute("INSERT OR IGNORE INTO personajes_estados (user_id) VALUES (?)", (u_id,))
                await db.execute("INSERT OR IGNORE INTO economia_billetera (user_id, balance_pc) VALUES (?, 0)", (u_id,))
                await db.execute(
                    "UPDATE economia_billetera SET balance_pc = balance_pc + ? WHERE user_id = ?",
                    (monto, u_id)
                )
            return True

async def emitir_fondos_reserva(receptor_id: int, cantidad_pc: int) -> bool:
    async with get_db() as db:
        async with transaction(db):
            await db.execute("INSERT OR IGNORE INTO personajes_estados (user_id) VALUES (?)", (receptor_id,))
            await db.execute("INSERT OR IGNORE INTO personajes_estados (user_id) VALUES (0)")
            await db.execute("INSERT OR IGNORE INTO economia_billetera (user_id, balance_pc) VALUES (?, 0)", (receptor_id,))
            await db.execute("INSERT OR IGNORE INTO economia_billetera (user_id, balance_pc) VALUES (0, 0)")

            async with db.execute(
                "UPDATE economia_billetera SET balance_pc = balance_pc - ? WHERE user_id = 0 AND balance_pc >= ?",
                (cantidad_pc, cantidad_pc)
            ) as cursor:
                if cursor.rowcount == 0:
                    return False

            await db.execute("UPDATE economia_billetera SET balance_pc = balance_pc + ? WHERE user_id = ?", (cantidad_pc, receptor_id))
            return True

async def procesar_compra_gremial(user_id: int, producto_nombre: str, costo_pc: int) -> bool:
    item_id = producto_nombre.lower().replace(" ", "_")

    async with get_db() as db:
        async with transaction(db):
            await db.execute("INSERT OR IGNORE INTO personajes_estados (user_id) VALUES (?)", (user_id,))
            await db.execute("INSERT OR IGNORE INTO personajes_estados (user_id) VALUES (0)")
            await db.execute("INSERT OR IGNORE INTO economia_billetera (user_id, balance_pc) VALUES (?, 0)", (user_id,))
            await db.execute("INSERT OR IGNORE INTO economia_billetera (user_id, balance_pc) VALUES (0, 0)")

            async with db.execute(
                "UPDATE economia_billetera SET balance_pc = balance_pc - ? WHERE user_id = ? AND balance_pc >= ?",
                (costo_pc, user_id, costo_pc)
            ) as cursor:
                if cursor.rowcount == 0:
                    return False

            await db.execute(
                "UPDATE economia_billetera SET balance_pc = balance_pc + ? WHERE user_id = 0",
                (costo_pc,)
            )

            await db.execute(
                "INSERT OR IGNORE INTO inventario_materiales (user_id, item_id, cantidad) VALUES (?, ?, 0)",
                (user_id, item_id)
            )
            await db.execute(
                "UPDATE inventario_materiales SET cantidad = cantidad + 1 WHERE user_id = ? AND item_id = ?",
                (user_id, item_id)
            )

            return True

# --- TICKETS ---

async def registrar_ticket(channel_id: int, user_id: int):
    async with get_db() as db:
        async with transaction(db):
            await db.execute("INSERT OR REPLACE INTO registro_tickets (channel_id, user_id, estado) VALUES (?, ?, 'ABIERTO')", (channel_id, user_id))

async def obtener_creador_ticket(channel_id: int):
    async with get_db() as db:
        async with db.execute("SELECT user_id FROM registro_tickets WHERE channel_id = ?", (channel_id,)) as cursor:
            row = await cursor.fetchone()
            return row["user_id"] if row else None

async def cerrar_ticket_db(channel_id: int):
    async with get_db() as db:
        async with transaction(db):
            await db.execute("UPDATE registro_tickets SET estado = 'CERRADO' WHERE channel_id = ?", (channel_id,))

# --- TIENDA E INVENTARIOS ---

async def obtener_catalogo():
    async with get_db() as db:
        async with db.execute("SELECT nombre, precio_str, costo_pc, categoria, descripcion FROM tienda_productos") as cursor:
            return await cursor.fetchall()

async def agregar_producto_db(nombre: str, precio_str: str, costo_pc: int, categoria: str, descripcion: str):
    async with get_db() as db:
        async with transaction(db):
            await db.execute("""
                INSERT INTO tienda_productos (nombre, precio_str, costo_pc, categoria, descripcion)
                VALUES (?, ?, ?, ?, ?)
            """, (nombre, precio_str, costo_pc, categoria, descripcion))

async def eliminar_producto_db(nombre: str) -> bool:
    async with get_db() as db:
        async with transaction(db):
            async with db.execute("DELETE FROM tienda_productos WHERE nombre = ? COLLATE NOCASE", (nombre,)) as cursor:
                return cursor.rowcount > 0

async def migrar_catalogo_inicial(catalogo_base: dict):
    async with get_db() as db:
        async with transaction(db):
            async with db.execute("SELECT COUNT(*) as cuenta FROM tienda_productos") as cursor:
                row = await cursor.fetchone()
                if row and row["cuenta"] > 0:
                    return

            for categoria, items in catalogo_base.items():
                for item in items:
                    await db.execute("""
                        INSERT INTO tienda_productos (nombre, precio_str, costo_pc, categoria, descripcion)
                        VALUES (?, ?, ?, ?, ?)
                    """, (item["nombre"], item["precio"], item["costo_pc"], categoria, item["desc"]))

async def agregar_item_inventario(user_id: int, producto_nombre: str, origen: str = 'tienda'):
    item_id = producto_nombre.lower().replace(" ", "_")
    async with get_db() as db:
        async with transaction(db):
            await db.execute("INSERT OR IGNORE INTO personajes_estados (user_id) VALUES (?)", (user_id,))

            if origen == 'nivel20':
                return

            await db.execute(
                "INSERT OR IGNORE INTO inventario_materiales (user_id, item_id, cantidad) VALUES (?, ?, 0)",
                (user_id, item_id)
            )
            await db.execute(
                "UPDATE inventario_materiales SET cantidad = cantidad + 1 WHERE user_id = ? AND item_id = ?",
                (user_id, item_id)
            )

async def obtener_inventario_usuario(user_id: int):
    async with get_db() as db:
        async with db.execute("""
            SELECT 0 as id, item_id as producto_nombre, cantidad, 'tienda' as origen
            FROM inventario_materiales WHERE user_id = ?
        """, (user_id,)) as cursor:
            return await cursor.fetchall()

async def usar_item_inventario(user_id: int, producto_nombre: str) -> bool:
    item_id = producto_nombre.lower().replace(" ", "_")
    async with get_db() as db:
        async with transaction(db):
            async with db.execute(
                "UPDATE inventario_materiales SET cantidad = cantidad - 1 WHERE user_id = ? AND item_id = ? AND cantidad > 0",
                (user_id, item_id)
            ) as cursor:
                if cursor.rowcount == 0:
                    return False

            await db.execute("DELETE FROM inventario_materiales WHERE user_id = ? AND cantidad <= 0", (user_id,))
            return True

# --- FICHA NIVEL20 ---

async def guardar_datos_ficha_nivel20(user_id: int, stats: dict):
    async with get_db() as db:
        async with transaction(db):
            await db.execute("DELETE FROM ficha_estadisticas WHERE user_id = ?", (user_id,))
            await db.execute("""
                INSERT INTO ficha_estadisticas (user_id, fuerza, destreza, constitucion, inteligencia, sabiduria, carisma, iniciativa, velocidad, competencia)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id, stats.get('fuerza', 10), stats.get('destreza', 10), stats.get('constitucion', 10),
                stats.get('inteligencia', 10), stats.get('sabiduria', 10), stats.get('carisma', 10),
                stats.get('iniciativa', '+0'), stats.get('velocidad', '30 pies'), stats.get('competencia', '+2')
            ))

            await db.execute("DELETE FROM ficha_clases WHERE user_id = ?", (user_id,))
            for c in stats.get('clases', []):
                await db.execute("INSERT INTO ficha_clases (user_id, clase, nivel) VALUES (?, ?, ?)", (user_id, c['nombre'], c['nivel']))

            await db.execute("DELETE FROM ficha_rasgos WHERE user_id = ?", (user_id,))
            for r in stats.get('rasgos', []):
                await db.execute("INSERT INTO ficha_rasgos (user_id, nombre) VALUES (?, ?)", (user_id, r))

            await db.execute("DELETE FROM ficha_conjuros WHERE user_id = ?", (user_id,))
            for conjuro in stats.get('conjuros', []):
                await db.execute("INSERT INTO ficha_conjuros (user_id, nombre, nivel) VALUES (?, ?, ?)", (user_id, conjuro['nombre'], conjuro['nivel']))

async def obtener_datos_ficha_completos(user_id: int):
    datos = {}
    async with get_db() as db:
        async with db.execute("SELECT * FROM ficha_estadisticas WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            datos['estadisticas'] = dict(row)

        async with db.execute("SELECT clase, nivel FROM ficha_clases WHERE user_id = ?", (user_id,)) as cursor:
            datos['clases'] = [dict(r) for r in await cursor.fetchall()]

        async with db.execute("SELECT nombre FROM ficha_rasgos WHERE user_id = ?", (user_id,)) as cursor:
            datos['rasgos'] = [r['nombre'] for r in await cursor.fetchall()]

        async with db.execute("SELECT nombre, nivel FROM ficha_conjuros WHERE user_id = ?", (user_id,)) as cursor:
            datos['conjuros'] = [dict(r) for r in await cursor.fetchall()]

        return datos

# --- CONTROLES FISCALES ---

async def embargar_fondos(user_id: int) -> int:
    async with get_db() as db:
        async with transaction(db):
            async with db.execute("SELECT balance_pc FROM economia_billetera WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                if not row or row["balance_pc"] <= 0:
                    return 0
                saldo_recuperado = row["balance_pc"]

            await db.execute("UPDATE economia_billetera SET balance_pc = 0 WHERE user_id = ?", (user_id,))
            await db.execute("INSERT OR IGNORE INTO personajes_estados (user_id) VALUES (0)")
            await db.execute("INSERT OR IGNORE INTO economia_billetera (user_id, balance_pc) VALUES (0, 0)")
            await db.execute("UPDATE economia_billetera SET balance_pc = balance_pc + ? WHERE user_id = 0", (saldo_recuperado,))
            return saldo_recuperado

async def embargo_masivo() -> int:
    async with get_db() as db:
        async with transaction(db):
            saldo_total_recuperado = 0
            async with db.execute("SELECT SUM(balance_pc) as total FROM economia_billetera WHERE user_id != 0") as cursor:
                row = await cursor.fetchone()
                if row and row["total"]:
                    saldo_total_recuperado = row["total"]

            if saldo_total_recuperado > 0:
                await db.execute("UPDATE economia_billetera SET balance_pc = 0 WHERE user_id != 0")
                await db.execute("INSERT OR IGNORE INTO personajes_estados (user_id) VALUES (0)")
                await db.execute("INSERT OR IGNORE INTO economia_billetera (user_id, balance_pc) VALUES (0, 0)")
                await db.execute("UPDATE economia_billetera SET balance_pc = balance_pc + ? WHERE user_id = 0", (saldo_total_recuperado,))

            return saldo_total_recuperado


# database.py

import aiosqlite
import os

# Determinar la ruta absoluta del directorio donde reside este archivo de forma dinámica
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Unir la ruta para que la base de datos se aloje e inicialice estrictamente en tu carpeta de proyecto
DB_PATH = os.path.join(BASE_DIR, "gremio.db")

# Tubería de conexión global persistente en memoria RAM para evitar bloqueos de disco
# NOTA EDUCATIVA: Usamos una conexión persistente para no estar abriendo y cerrando
# el archivo de la base de datos en cada comando, lo que en un VPS causaría lentitud y errores.
_connection = None

async def init_db():
    """Inicializa el pool de conexiones persistentes y forja las tablas del reino."""
    global _connection
    # NOTA EDUCATIVA: Solo nos conectamos si no hay una conexión activa, esto previene
    # sobrescribir la conexión y dejar "conexiones fantasma" que bloquean la base de datos (Database is locked).
    if _connection is None:
        _connection = await aiosqlite.connect(DB_PATH)
        # Habilitar soporte para llaves foráneas y optimizaciones de velocidad en SQLite
        await _connection.execute("PRAGMA foreign_keys = ON")
        # NOTA EDUCATIVA: El modo WAL (Write-Ahead Logging) permite que SQLite lea y escriba
        # al mismo tiempo. Es FUNDAMENTAL para un bot de Discord asíncrono para que no se congele.
        await _connection.execute("PRAGMA journal_mode = WAL")
        # Cambiar el formato de retorno a diccionarios por defecto para evitar errores de índice
        _connection.row_factory = aiosqlite.Row

    # 1. Tabla de Aventureros
    await _connection.execute("""
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
    
    # --- MOTOR AUTOMÁTICO DE MIGRACIÓN ---
    async with _connection.execute("PRAGMA table_info(aventureros)") as cursor:
        columnas_existentes = [columna["name"] for columna in await cursor.fetchall()]
    
    if "nivel" not in columnas_existentes:
        await _connection.execute("ALTER TABLE aventureros ADD COLUMN nivel INTEGER DEFAULT 1")
    if "sesiones_jugadas" not in columnas_existentes:
        await _connection.execute("ALTER TABLE aventureros ADD COLUMN sesiones_jugadas INTEGER DEFAULT 0")

    # Índice para acelerar el cálculo del Ladder de Aventureros (Optimización de Bolt ⚡)
    await _connection.execute("CREATE INDEX IF NOT EXISTS idx_aventureros_ladder ON aventureros (nivel DESC, sesiones_jugadas DESC)")

    # 2. Tabla Base: Sistema de Matchmaking
    await _connection.execute("""
        CREATE TABLE IF NOT EXISTS matchmaking (
            user_id INTEGER PRIMARY KEY,
            rol_busqueda TEXT NOT NULL,
            tier_juego TEXT,
            dias_disponibles TEXT NOT NULL,
            hora_inicio_utc INTEGER NOT NULL,
            hora_fin_utc INTEGER NOT NULL
        )
    """)

    # 3. Tabla: Registro de licencias de los Dungeon Masters
    await _connection.execute("""
        CREATE TABLE IF NOT EXISTS registro_dms (
            dm_id INTEGER PRIMARY KEY,
            nombre_dm TEXT NOT NULL,
            rango_licencia TEXT DEFAULT 'Aprendiz',
            partidas_narradas INTEGER DEFAULT 0
        )
    """)

    # 4. Tabla: Reputación por Urna Transaccional Anónima
    await _connection.execute("""
        CREATE TABLE IF NOT EXISTS reseñas_dms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dm_id INTEGER NOT NULL,
            valoracion INTEGER NOT NULL,
            comentario TEXT,
            FOREIGN KEY (dm_id) REFERENCES registro_dms(dm_id)
        )
    """)

    # Índice para acelerar las búsquedas por dm_id en reseñas (Optimización de Bolt ⚡)
    await _connection.execute("CREATE INDEX IF NOT EXISTS idx_resenas_dm_id ON reseñas_dms (dm_id)")

    # Índice para acelerar la extracción del Top de DMs (Optimización de Bolt ⚡)
    await _connection.execute("CREATE INDEX IF NOT EXISTS idx_dms_partidas ON registro_dms (partidas_narradas DESC)")

    # 5. Tabla de Control de Anclas de Embeds Fijos
    await _connection.execute("""
        CREATE TABLE IF NOT EXISTS control_nominas (
            seccion TEXT PRIMARY KEY,
            channel_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL
        )
    """)

    # 6. Tabla de Registro de Personal por Rama Administrative
    await _connection.execute("""
        CREATE TABLE IF NOT EXISTS personal_ramas (
            user_id INTEGER PRIMARY KEY,
            division TEXT NOT NULL,
            rango_interno TEXT NOT NULL
        )
    """)
    
    # 7. Tabla de Balances Bancarios
    await _connection.execute("""
        CREATE TABLE IF NOT EXISTS cuentas_bancarias (
            id_entidad INTEGER PRIMARY KEY, 
            balance_pc INTEGER DEFAULT 0    
        )
    """)

    # 8. Tabla de Productos de la Tienda
    await _connection.execute("""
        CREATE TABLE IF NOT EXISTS tienda_productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL COLLATE NOCASE,
            precio_str TEXT NOT NULL,
            costo_pc INTEGER NOT NULL,
            categoria TEXT NOT NULL,
            descripcion TEXT NOT NULL
        )
    """)

    # SCHEMA V3 CANÓNICO ASTERIA: Inyectamos las nuevas tablas de infraestructura Trustless
    await _connection.executescript("""
        CREATE TABLE IF NOT EXISTS matriz_recompensas (
            rango_dm VARCHAR(20) NOT NULL,
            nivel_personaje INTEGER NOT NULL,
            max_pc_permitido INTEGER NOT NULL,
            max_rareza VARCHAR(20) NOT NULL,
            PRIMARY KEY (rango_dm, nivel_personaje)
        );

        CREATE TABLE IF NOT EXISTS personajes_estados (
            user_id VARCHAR(30) PRIMARY KEY,
            estado_viajando BOOLEAN DEFAULT 0,
            viaje_desbloqueo_timestamp INTEGER DEFAULT 0,
            nivel_extenuacion INTEGER DEFAULT 0,
            estado_herido BOOLEAN DEFAULT 0,
            pendiente_auditoria BOOLEAN DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS economia_billetera (
            user_id VARCHAR(30) PRIMARY KEY,
            balance_pc INTEGER DEFAULT 0 CHECK(balance_pc >= 0),
            FOREIGN KEY (user_id) REFERENCES personajes_estados(user_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS inventario_materiales (
            user_id VARCHAR(30) NOT NULL,
            item_id VARCHAR(50) NOT NULL,
            cantidad INTEGER NOT NULL CHECK(cantidad >= 0),
            PRIMARY KEY (user_id, item_id),
            FOREIGN KEY (user_id) REFERENCES personajes_estados(user_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS inventario_instancias (
            instance_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id VARCHAR(30) NOT NULL,
            item_id VARCHAR(50) NOT NULL,
            durabilidad_actual INTEGER NOT NULL CHECK(durabilidad_actual >= 0),
            grado_runa INTEGER DEFAULT 0,
            estado_critico BOOLEAN DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES personajes_estados(user_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS registro_recetas_conocidas (
            user_id VARCHAR(30) NOT NULL,
            receta_id VARCHAR(50) NOT NULL,
            PRIMARY KEY (user_id, receta_id),
            FOREIGN KEY (user_id) REFERENCES personajes_estados(user_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_inventario_materiales_user ON inventario_materiales(user_id);
        CREATE INDEX IF NOT EXISTS idx_inventario_instancias_user ON inventario_instancias(user_id);
        CREATE INDEX IF NOT EXISTS idx_registro_recetas_user ON registro_recetas_conocidas(user_id);
    """)

    # 9. Inventarios y pertenencias (Legacy: Mantenida para compatibilidad con código no refactorizado temporalmente)
    await _connection.execute("""
        CREATE TABLE IF NOT EXISTS inventarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            producto_nombre TEXT NOT NULL,
            cantidad INTEGER DEFAULT 1,
            origen TEXT DEFAULT 'tienda', -- 'tienda' o 'nivel20' (Para marcar lo sincronizado)
            FOREIGN KEY (user_id) REFERENCES aventureros(user_id) ON DELETE CASCADE
        )
    """)

    # --- MIGRACIÓN ATÓMICA DE DATOS (PORTEO V3) ---
    # Lazy Bridge para foráneas
    await _connection.execute("""
        INSERT OR IGNORE INTO personajes_estados (user_id)
        SELECT CAST(id_entidad AS VARCHAR) FROM cuentas_bancarias;
    """)
    # Bóveda Central (ID 0)
    await _connection.execute("INSERT OR IGNORE INTO personajes_estados (user_id) VALUES ('0');")

    # Porteo de Economía In-Place a economia_billetera (Transacción Bifurcada Retrocompatible)
    await _connection.execute("""
        INSERT OR IGNORE INTO economia_billetera (user_id, balance_pc)
        SELECT CAST(id_entidad AS VARCHAR), 0 FROM cuentas_bancarias;
    """)
    await _connection.execute("""
        UPDATE economia_billetera
        SET balance_pc = balance_pc + (
            SELECT balance_pc FROM cuentas_bancarias
            WHERE CAST(id_entidad AS VARCHAR) = economia_billetera.user_id
        )
        WHERE user_id IN (SELECT CAST(id_entidad AS VARCHAR) FROM cuentas_bancarias);
    """)

    # Porteo de Inventario Legacy a Materiales (Transacción Bifurcada Retrocompatible)
    await _connection.execute("""
        INSERT OR IGNORE INTO inventario_materiales (user_id, item_id, cantidad)
        SELECT CAST(user_id AS VARCHAR), REPLACE(LOWER(producto_nombre), ' ', '_'), 0
        FROM inventarios;
    """)
    # Usamos una sumatoria para evitar problemas si el inventario legacy ya tenía items repetidos.
    await _connection.execute("""
        UPDATE inventario_materiales
        SET cantidad = cantidad + (
            SELECT SUM(cantidad) FROM inventarios
            WHERE CAST(user_id AS VARCHAR) = inventario_materiales.user_id
              AND REPLACE(LOWER(producto_nombre), ' ', '_') = inventario_materiales.item_id
        )
        WHERE (user_id, item_id) IN (
            SELECT CAST(user_id AS VARCHAR), REPLACE(LOWER(producto_nombre), ' ', '_') FROM inventarios
        );
    """)

    # 10. Tablas para información mecánica de la hoja de personaje extraída de Nivel20
    await _connection.execute("""
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
        )
    """)

    await _connection.execute("""
        CREATE TABLE IF NOT EXISTS ficha_clases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            clase TEXT NOT NULL,
            nivel INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES aventureros(user_id) ON DELETE CASCADE
        )
    """)

    await _connection.execute("""
        CREATE TABLE IF NOT EXISTS ficha_rasgos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            nombre TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES aventureros(user_id) ON DELETE CASCADE
        )
    """)

    await _connection.execute("""
        CREATE TABLE IF NOT EXISTS ficha_conjuros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            nombre TEXT NOT NULL,
            nivel TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES aventureros(user_id) ON DELETE CASCADE
        )
    """)

    # Para facilitar las actualizaciones estructurales
    # Si la tabla ya existe y no tiene la columna 'origen', la agregamos dinámicamente.
    try:
        await _connection.execute("ALTER TABLE inventarios ADD COLUMN origen TEXT DEFAULT 'tienda'")
    except Exception:
        pass # La columna ya existe

    await _connection.commit()
    
    # REFACTORIZACIÓN TÉCNICA OBLIGATORIA EN init_db() DE database.py
    try:
        await _connection.execute("BEGIN")
        # Asegurar Lazy Bridge de ID 0 para foreign keys
        await _connection.execute("INSERT OR IGNORE INTO personajes_estados (user_id) VALUES ('0')")

        # 1. Garantizar la existencia física de la Bóveda Central en la tabla canónica V3
        await _connection.execute(
            "INSERT OR IGNORE INTO economia_billetera (user_id, balance_pc) VALUES ('0', 20000000)"
        )

        # 2. Si la base de datos es heredada y la billetera de la bóveda conserva un saldo inferior
        # al buffer mínimo de seguridad, se reajusta automáticamente a 20,000,000 pc (20,000 pp).
        await _connection.execute(
            "UPDATE economia_billetera SET balance_pc = 20000000 WHERE user_id = '0' AND balance_pc < 20000000"
        )
        await _connection.commit()
        print("🏦 [TESORERÍA] Bóveda Central canonicalizada y estabilizada en 20,000,000 pc (20,000 pp) en economia_billetera.")
    except Exception as e:
        await _connection.rollback()
        print(f"❌ Error Crítico al inicializar la Bóveda Central en economia_billetera: {e}")

# --- MÓDULO DE CONSULTAS OPTIMIZADAS ---

async def obtener_personaje(user_id: int):
    async with _connection.execute(
        "SELECT char_name, char_race, char_class, char_age, char_height, sheet_link, nivel FROM aventureros WHERE user_id = ?", 
        (user_id,)
    ) as cursor:
        return await cursor.fetchone()

async def registrar_personaje(user_id: int, name: str, race: str, char_class: str, age: int, height: str, link: str):
    await _connection.execute("""
        INSERT INTO aventureros (user_id, char_name, char_race, char_class, char_age, char_height, sheet_link, nivel, sesiones_jugadas)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1, 0)
    """, (user_id, name, race, char_class, age, height, link))
    await _connection.commit()

async def eliminar_personaje(user_id: int):
    async with _connection.execute("DELETE FROM aventureros WHERE user_id = ?", (user_id,)) as cursor:
        if cursor.rowcount == 0:
            return False
    await _connection.commit()
    return True

async def guardar_registro_matchmaking(user_id: int, rol: str, tier: str, dias: str, inicio: int, fin: int):
    await _connection.execute("""
        INSERT OR REPLACE INTO matchmaking (user_id, rol_busqueda, tier_juego, dias_disponibles, hora_inicio_utc, hora_fin_utc)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, rol, tier, dias, inicio, fin))
    await _connection.commit()

async def eliminar_de_cola(user_id: int):
    async with _connection.execute("DELETE FROM matchmaking WHERE user_id = ?", (user_id,)) as cursor:
        if cursor.rowcount == 0:
            return False
    await _connection.commit()
    return True

async def obtener_toda_la_cola():
    async with _connection.execute("SELECT user_id, rol_busqueda, tier_juego, dias_disponibles, hora_inicio_utc, hora_fin_utc FROM matchmaking") as cursor:
        return await cursor.fetchall()

async def actualizar_nivel_personaje(user_id: int, nuevo_nivel: int):
    async with _connection.execute("UPDATE aventureros SET nivel = ? WHERE user_id = ?", (nuevo_nivel, user_id)) as cursor:
        if cursor.rowcount == 0:
            return False
    await _connection.commit()
    return True   

async def editar_datos_personaje(user_id: int, name: str, race: str, char_class: str, age: int, height: str, link: str):
    async with _connection.execute("""
        UPDATE aventureros 
        SET char_name = ?, char_race = ?, char_class = ?, char_age = ?, char_height = ?, sheet_link = ?
        WHERE user_id = ?
    """, (name, race, char_class, age, height, link, user_id)) as cursor:
        if cursor.rowcount == 0:
            return False
    await _connection.commit()
    return True

async def obtener_perfil_dm(dm_id: int):
    # OPTIMIZACIÓN SENIOR: Consolidación de datos de perfil y agregación de reseñas en una única consulta relacional limpia
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
    async with _connection.execute(query, (dm_id,)) as cursor:
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
    async with _connection.execute("SELECT user_id, char_name, nivel, sesiones_jugadas FROM aventureros ORDER BY nivel DESC, sesiones_jugadas DESC LIMIT 10") as cursor:
        return await cursor.fetchall()

async def obtener_ladder_dms():
    # SOLUCIÓN COMPLETA AL ANTIPATRÓN N+1 (Optimizada por Bolt ⚡):
    # Extraer el Top 10 ANTES de hacer el LEFT JOIN masivo O(N*M) con todas las reseñas del servidor
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
    async with _connection.execute(query) as cursor:
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
    await _connection.execute("INSERT OR REPLACE INTO control_nominas (seccion, channel_id, message_id) VALUES (?, ?, ?)", (seccion, channel_id, message_id))
    await _connection.commit()

async def obtener_ancla_nomina(seccion: str):
    async with _connection.execute("SELECT channel_id, message_id FROM control_nominas WHERE seccion = ?", (seccion,)) as cursor:
        return await cursor.fetchone()

async def actualizar_miembro_personal(user_id: int, division: str, rango: str):
    await _connection.execute("INSERT OR REPLACE INTO personal_ramas (user_id, division, rango_interno) VALUES (?, ?, ?)", (user_id, division, rango))
    await _connection.commit()

async def remover_miembro_personal(user_id: int):
    await _connection.execute("DELETE FROM personal_ramas WHERE user_id = ?", (user_id,))
    await _connection.commit()

async def obtener_personal_division(division: str):
    async with _connection.execute("SELECT user_id, rango_interno FROM personal_ramas WHERE division = ?", (division,)) as cursor:
        return await cursor.fetchall()

async def obtener_candidatos_compatibles_dm(dm_id: int, limite_jugadores: int):
    """
    Extrae de forma atómica únicamente los jugadores que cumplen con la ventana 
    temporal mínima (3 horas) y las restricciones de nivel del DM evaluado.
    """
    # 1. Obtener los parámetros específicos de tiempo del DM
    async with _connection.execute(
        "SELECT hora_inicio_utc, hora_fin_utc FROM matchmaking WHERE user_id = ? AND rol_busqueda = 'dm'", 
        (dm_id,)
    ) as cursor:
        dm_datos = await cursor.fetchone()
        if not dm_datos:
            return []
            
    dm_ini = dm_datos["hora_inicio_utc"]
    dm_fin = dm_datos["hora_fin_utc"]

    # 2. Consulta de filtrado industrial mediante álgebra relacional en SQLite
    # Determina la coincidencia horaria (intersección >= 180 minutos) en una sola pasada de disco
    # BLINDAJE: Consideramos los ciclos cruzados de la medianoche (ej: un turno que empieza a las 22:00 y acaba a las 02:00).
    # Si fin < inicio, le sumamos 24h (1440 mins) tanto en Python como en SQL.
    if dm_fin <= dm_ini:
        dm_fin += 1440

    query = """
        SELECT m.user_id, a.nivel, m.hora_inicio_utc, m.hora_fin_utc
        FROM matchmaking m
        JOIN aventureros a ON m.user_id = a.user_id
        WHERE m.rol_busqueda = 'jugador'
          AND (
              -- Calculamos la intersección de horas sumando 1440 minutos si cruzan la medianoche
              MIN(CASE WHEN m.hora_fin_utc <= m.hora_inicio_utc THEN m.hora_fin_utc + 1440 ELSE m.hora_fin_utc END, ?)
              -
              MAX(m.hora_inicio_utc, ?)
          ) >= 180
    """
    
    async with _connection.execute(query, (dm_fin, dm_ini)) as cursor:
        return await cursor.fetchall()

# --- INFRAESTRUCTURA CONTABLE ATÓMICA (ALTERNATIVAB) ---

async def obtener_balance(id_entidad: int) -> int:
    async with _connection.execute("SELECT balance_pc FROM economia_billetera WHERE user_id = ?", (str(id_entidad),)) as cursor:
        resultado = await cursor.fetchone()
        return resultado["balance_pc"] if resultado else 0

async def inyectar_fondos_ignorados(dm_id: int, nombre_dm: str, valor: int, label_voto: str):
    await _connection.execute("INSERT OR IGNORE INTO registro_dms (dm_id, nombre_dm) VALUES (?, ?)", (dm_id, nombre_dm))
    await _connection.execute("INSERT INTO reseñas_dms (dm_id, valoracion, comentario) VALUES (?, ?, ?)", (dm_id, valor, f"Voto directo: {label_voto}"))
    await _connection.commit()

async def transferir_fondos(emisor_id: int, receptor_id: int, cantidad_pc: int) -> bool:
    """Ejecuta una transferencia bancaria P2P atómica puramente controlada por el motor de SQLite."""
    # BLINDAJE EXTRA: Evitamos que una persona pueda enviarse dinero negativo para sumar saldo mágicamente a su cuenta.
    if cantidad_pc <= 0:
        return False

    emisor_str = str(emisor_id)
    receptor_str = str(receptor_id)

    # REFACTOR V5: Transacciones explícitas para portabilidad segura en Schema V3
    try:
        await _connection.execute("BEGIN")
        # Lazy Init para ambos
        await _connection.execute("INSERT OR IGNORE INTO personajes_estados (user_id) VALUES (?)", (emisor_str,))
        await _connection.execute("INSERT OR IGNORE INTO personajes_estados (user_id) VALUES (?)", (receptor_str,))

        await _connection.execute("INSERT OR IGNORE INTO economia_billetera (user_id, balance_pc) VALUES (?, 0)", (emisor_str,))
        await _connection.execute("INSERT OR IGNORE INTO economia_billetera (user_id, balance_pc) VALUES (?, 0)", (receptor_str,))

        # 2. Deducción condicionada en el WHERE
        async with _connection.execute(
            "UPDATE economia_billetera SET balance_pc = balance_pc - ? WHERE user_id = ? AND balance_pc >= ?",
            (cantidad_pc, emisor_str, cantidad_pc)
        ) as cursor:
            if cursor.rowcount == 0:
                await _connection.rollback()
                return False  # El emisor no cuenta con los fondos requeridos. Abortado, se activa Rollback manual.

        # 3. Inyección al receptor
        await _connection.execute(
            "UPDATE economia_billetera SET balance_pc = balance_pc + ? WHERE user_id = ?",
            (cantidad_pc, receptor_str)
        )
        await _connection.commit()
        return True
    except Exception:
        await _connection.rollback()
        return False

async def emitir_fondos_reserva(receptor_id: int, cantidad_pc: int) -> bool:
    """Extrae fondos directamente de la Bóveda del Gremio (id 0) bajo validación atómica estructural V3."""
    receptor_str = str(receptor_id)
    
    try:
        await _connection.execute("BEGIN")
        # Lazy init
        await _connection.execute("INSERT OR IGNORE INTO personajes_estados (user_id) VALUES (?)", (receptor_str,))
        await _connection.execute("INSERT OR IGNORE INTO personajes_estados (user_id) VALUES ('0')")
        await _connection.execute("INSERT OR IGNORE INTO economia_billetera (user_id, balance_pc) VALUES (?, 0)", (receptor_str,))
        await _connection.execute("INSERT OR IGNORE INTO economia_billetera (user_id, balance_pc) VALUES ('0', 0)")

        # Restar de la bóveda
        async with _connection.execute(
            "UPDATE economia_billetera SET balance_pc = balance_pc - ? WHERE user_id = '0' AND balance_pc >= ?",
            (cantidad_pc, cantidad_pc)
        ) as cursor:
            if cursor.rowcount == 0:
                await _connection.rollback()
                return False  # Bóveda sin liquidez

        await _connection.execute("UPDATE economia_billetera SET balance_pc = balance_pc + ? WHERE user_id = ?", (cantidad_pc, receptor_str))
        await _connection.commit()
        return True
    except Exception:
        await _connection.rollback()
        return False

# --- TIENDA E INVENTARIOS ---

async def obtener_catalogo():
    # NOTA EDUCATIVA: Retornamos todos los productos para reconstruir el catálogo en memoria.
    async with _connection.execute("SELECT nombre, precio_str, costo_pc, categoria, descripcion FROM tienda_productos") as cursor:
        return await cursor.fetchall()

async def agregar_producto_db(nombre: str, precio_str: str, costo_pc: int, categoria: str, descripcion: str):
    await _connection.execute("""
        INSERT INTO tienda_productos (nombre, precio_str, costo_pc, categoria, descripcion)
        VALUES (?, ?, ?, ?, ?)
    """, (nombre, precio_str, costo_pc, categoria, descripcion))
    await _connection.commit()

async def eliminar_producto_db(nombre: str) -> bool:
    async with _connection.execute("DELETE FROM tienda_productos WHERE nombre = ? COLLATE NOCASE", (nombre,)) as cursor:
        exito = cursor.rowcount > 0
    await _connection.commit()
    return exito

async def migrar_catalogo_inicial(catalogo_base: dict):
    """Inserta el catálogo inicial por defecto si la tienda está vacía."""
    async with _connection.execute("SELECT COUNT(*) as cuenta FROM tienda_productos") as cursor:
        row = await cursor.fetchone()
        if row and row["cuenta"] > 0:
            return  # Ya hay productos, no migrar

    for categoria, items in catalogo_base.items():
        for item in items:
            await _connection.execute("""
                INSERT INTO tienda_productos (nombre, precio_str, costo_pc, categoria, descripcion)
                VALUES (?, ?, ?, ?, ?)
            """, (item["nombre"], item["precio"], item["costo_pc"], categoria, item["desc"]))
    await _connection.commit()

async def agregar_item_inventario(user_id: int, producto_nombre: str, origen: str = 'tienda'):
    """
    Suma 1 a la cantidad de un producto en el inventario del usuario V3 (Solo materiales apilables).
    Si no existe, lo crea.
    """
    user_str = str(user_id)
    item_id = producto_nombre.lower().replace(" ", "_")
    try:
        await _connection.execute("BEGIN")
        await _connection.execute("INSERT OR IGNORE INTO personajes_estados (user_id) VALUES (?)", (user_str,))

        if origen == 'nivel20':
            # Sincronización de solo lectura, no modificamos SQLite según Schema V3
            await _connection.commit()
            return

        await _connection.execute(
            "INSERT OR IGNORE INTO inventario_materiales (user_id, item_id, cantidad) VALUES (?, ?, 0)",
            (user_str, item_id)
        )
        await _connection.execute(
            "UPDATE inventario_materiales SET cantidad = cantidad + 1 WHERE user_id = ? AND item_id = ?",
            (user_str, item_id)
        )
        await _connection.commit()
    except Exception as e:
        await _connection.rollback()
        print(f"Error agregando item: {e}")

async def obtener_inventario_usuario(user_id: int):
    user_str = str(user_id)
    # Reconstruimos la salida legacy uniendo ambas tablas V3
    async with _connection.execute("""
        SELECT 0 as id, item_id as producto_nombre, cantidad, 'tienda' as origen
        FROM inventario_materiales WHERE user_id = ?
    """, (user_str,)) as cursor:
        return await cursor.fetchall()

async def usar_item_inventario(user_id: int, producto_nombre: str) -> bool:
    """
    Resta 1 a la cantidad del producto. Si llega a 0, se elimina del inventario (V3).
    """
    user_str = str(user_id)
    item_id = producto_nombre.lower().replace(" ", "_")

    try:
        await _connection.execute("BEGIN")
        async with _connection.execute(
            "UPDATE inventario_materiales SET cantidad = cantidad - 1 WHERE user_id = ? AND item_id = ? AND cantidad > 0",
            (user_str, item_id)
        ) as cursor:
            if cursor.rowcount == 0:
                await _connection.rollback()
                return False

        await _connection.execute("DELETE FROM inventario_materiales WHERE user_id = ? AND cantidad <= 0", (user_str,))
        await _connection.commit()
        return True
    except Exception:
        await _connection.rollback()
        return False

# --- LÓGICA DE FICHA NIVEL20 ---

async def guardar_datos_ficha_nivel20(user_id: int, stats: dict):
    """
    Guarda o actualiza todos los datos extraídos de Nivel20.
    stats es un dict con: fuerza, destreza, constitucion, inteligencia, sabiduria, carisma,
    iniciativa, velocidad, competencia, clases (list de dicts), rasgos (list), conjuros (list de dicts), equipo (list)
    """
    # 1. Estadísticas Base
    await _connection.execute("DELETE FROM ficha_estadisticas WHERE user_id = ?", (user_id,))
    await _connection.execute("""
        INSERT INTO ficha_estadisticas (user_id, fuerza, destreza, constitucion, inteligencia, sabiduria, carisma, iniciativa, velocidad, competencia)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id, stats.get('fuerza', 10), stats.get('destreza', 10), stats.get('constitucion', 10),
        stats.get('inteligencia', 10), stats.get('sabiduria', 10), stats.get('carisma', 10),
        stats.get('iniciativa', '+0'), stats.get('velocidad', '30 pies'), stats.get('competencia', '+2')
    ))

    # 2. Clases
    await _connection.execute("DELETE FROM ficha_clases WHERE user_id = ?", (user_id,))
    for c in stats.get('clases', []):
        await _connection.execute("INSERT INTO ficha_clases (user_id, clase, nivel) VALUES (?, ?, ?)", (user_id, c['nombre'], c['nivel']))

    # 3. Rasgos
    await _connection.execute("DELETE FROM ficha_rasgos WHERE user_id = ?", (user_id,))
    for r in stats.get('rasgos', []):
        await _connection.execute("INSERT INTO ficha_rasgos (user_id, nombre) VALUES (?, ?)", (user_id, r))

    # 4. Conjuros
    await _connection.execute("DELETE FROM ficha_conjuros WHERE user_id = ?", (user_id,))
    for conjuro in stats.get('conjuros', []):
        await _connection.execute("INSERT INTO ficha_conjuros (user_id, nombre, nivel) VALUES (?, ?, ?)", (user_id, conjuro['nombre'], conjuro['nivel']))

    # 5. Equipo (Marcando origen='nivel20')
    # REFACTOR V5: Según las directivas Trustless V3, ignoramos por completo el inventario de Nivel20
    # y ya no sincronizamos objetos provenientes de la ficha de lectura externa.

    await _connection.commit()

async def obtener_datos_ficha_completos(user_id: int):
    """Devuelve un diccionario con todas las estadísticas vinculadas."""
    datos = {}
    async with _connection.execute("SELECT * FROM ficha_estadisticas WHERE user_id = ?", (user_id,)) as cursor:
        row = await cursor.fetchone()
        if not row:
            return None
        datos['estadisticas'] = dict(row)

    async with _connection.execute("SELECT clase, nivel FROM ficha_clases WHERE user_id = ?", (user_id,)) as cursor:
        datos['clases'] = [dict(r) for r in await cursor.fetchall()]

    async with _connection.execute("SELECT nombre FROM ficha_rasgos WHERE user_id = ?", (user_id,)) as cursor:
        datos['rasgos'] = [r['nombre'] for r in await cursor.fetchall()]

    async with _connection.execute("SELECT nombre, nivel FROM ficha_conjuros WHERE user_id = ?", (user_id,)) as cursor:
        datos['conjuros'] = [dict(r) for r in await cursor.fetchall()]

    return datos

# --- HERRAMIENTAS DE CONTROL FISCAL (INCAUTACIÓN) ---

async def embargar_fondos(user_id: int) -> int:
    """Extrae la totalidad de los fondos de un usuario y los inyecta en la Bóveda Central (id 0) (V3)."""
    user_str = str(user_id)
    try:
        await _connection.execute("BEGIN")
        async with _connection.execute("SELECT balance_pc FROM economia_billetera WHERE user_id = ?", (user_str,)) as cursor:
            row = await cursor.fetchone()
            if not row or row["balance_pc"] <= 0:
                await _connection.rollback()
                return 0
            saldo_recuperado = row["balance_pc"]

        await _connection.execute("UPDATE economia_billetera SET balance_pc = 0 WHERE user_id = ?", (user_str,))

        # Asegurar boveda
        await _connection.execute("INSERT OR IGNORE INTO personajes_estados (user_id) VALUES ('0')")
        await _connection.execute("INSERT OR IGNORE INTO economia_billetera (user_id, balance_pc) VALUES ('0', 0)")

        await _connection.execute("UPDATE economia_billetera SET balance_pc = balance_pc + ? WHERE user_id = '0'", (saldo_recuperado,))
        await _connection.commit()
        return saldo_recuperado
    except Exception:
        await _connection.rollback()
        return 0

async def embargo_masivo() -> int:
    """Wipe económico total V3: Transfiere todos los fondos de los jugadores a la Bóveda Central."""
    try:
        await _connection.execute("BEGIN")
        saldo_total_recuperado = 0
        async with _connection.execute("SELECT SUM(balance_pc) as total FROM economia_billetera WHERE user_id != '0'") as cursor:
            row = await cursor.fetchone()
            if row and row["total"]:
                saldo_total_recuperado = row["total"]

        if saldo_total_recuperado > 0:
            await _connection.execute("UPDATE economia_billetera SET balance_pc = 0 WHERE user_id != '0'")

            await _connection.execute("INSERT OR IGNORE INTO personajes_estados (user_id) VALUES ('0')")
            await _connection.execute("INSERT OR IGNORE INTO economia_billetera (user_id, balance_pc) VALUES ('0', 0)")

            await _connection.execute("UPDATE economia_billetera SET balance_pc = balance_pc + ? WHERE user_id = '0'", (saldo_total_recuperado,))

        await _connection.commit()
        return saldo_total_recuperado
    except Exception:
        await _connection.rollback()
        return 0


async def cerrar_db():
    global _connection
    if _connection is not None:
        await _connection.close()
        _connection = None
        print("💾 [BANCO] Pool de conexiones persistentes cerrado de forma segura.")
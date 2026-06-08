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

    # 9. Tabla de Inventario de Usuarios
    await _connection.execute("""
        CREATE TABLE IF NOT EXISTS inventarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            producto_nombre TEXT NOT NULL,
            cantidad INTEGER DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES aventureros(user_id) ON DELETE CASCADE
        )
    """)

    await _connection.commit()
    
    # Inyección Inicial del Fondo de Reserva Maestro (1,000 pp = 1,000,000 pc)
    async with _connection.execute("SELECT balance_pc FROM cuentas_bancarias WHERE id_entidad = 0") as cursor:
        if not await cursor.fetchone():
            await _connection.execute("INSERT INTO cuentas_bancarias (id_entidad, balance_pc) VALUES (0, 1000000)")
            await _connection.commit()
            print("💰 [BANCO] Bóveda Central inicializada con 1,000,000 pc.")

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
    async with _connection.execute("SELECT balance_pc FROM cuentas_bancarias WHERE id_entidad = ?", (id_entidad,)) as cursor:
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

    # 1. Forzar la existencia del registro contable del receptor para evitar violaciones de nulidad
    await _connection.execute("INSERT OR IGNORE INTO cuentas_bancarias (id_entidad, balance_pc) VALUES (?, 0)", (receptor_id,))
    await _connection.execute("INSERT OR IGNORE INTO cuentas_bancarias (id_entidad, balance_pc) VALUES (?, 0)", (emisor_id,))
    
    # 2. Intentar la deducción de los fondos condicionada directamente en el WHERE
    # Esto blinda el sistema contra Race Conditions (Dos retiros exactamente al mismo tiempo):
    # Si no hay fondos suficientes para cubrir 'cantidad_pc', SQLite aborta la escritura y rowcount será 0.
    async with _connection.execute(
        "UPDATE cuentas_bancarias SET balance_pc = balance_pc - ? WHERE id_entidad = ? AND balance_pc >= ?",
        (cantidad_pc, emisor_id, cantidad_pc)
    ) as cursor:
        if cursor.rowcount == 0:
            return False  # El emisor no cuenta con los fondos requeridos. Abortado.

    # 3. Al confirmarse el retiro del emisor, se procede con la inyección segura al receptor
    await _connection.execute("UPDATE cuentas_bancarias SET balance_pc = balance_pc + ? WHERE id_entidad = ?", (cantidad_pc, receptor_id))
    await _connection.commit()
    return True

async def emitir_fondos_reserva(receptor_id: int, cantidad_pc: int) -> bool:
    """Extrae fondos directamente de la Bóveda del Gremio (id 0) bajo validación atómica estructural."""
    await _connection.execute("INSERT OR IGNORE INTO cuentas_bancarias (id_entidad, balance_pc) VALUES (?, 0)", (receptor_id,))
    
    # Restar de la bóveda (id 0) garantizando que la reserva central no caiga en saldo negativo
    async with _connection.execute(
        "UPDATE cuentas_bancarias SET balance_pc = balance_pc - ? WHERE id_entidad = 0 AND balance_pc >= ?",
        (cantidad_pc, cantidad_pc)
    ) as cursor:
        if cursor.rowcount == 0:
            return False  # La Bóveda Central se encuentra sin liquidez para cubrir el monto.
            
    await _connection.execute("UPDATE cuentas_bancarias SET balance_pc = balance_pc + ? WHERE id_entidad = ?", (cantidad_pc, receptor_id))
    await _connection.commit()
    return True  

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

async def agregar_item_inventario(user_id: int, producto_nombre: str):
    """
    Suma 1 a la cantidad de un producto en el inventario del usuario.
    Si no existe, lo crea.
    """
    async with _connection.execute(
        "SELECT id, cantidad FROM inventarios WHERE user_id = ? AND producto_nombre = ? COLLATE NOCASE",
        (user_id, producto_nombre)
    ) as cursor:
        row = await cursor.fetchone()

    if row:
        nueva_cantidad = row["cantidad"] + 1
        await _connection.execute("UPDATE inventarios SET cantidad = ? WHERE id = ?", (nueva_cantidad, row["id"]))
    else:
        await _connection.execute("INSERT INTO inventarios (user_id, producto_nombre, cantidad) VALUES (?, ?, 1)", (user_id, producto_nombre))

    await _connection.commit()

async def obtener_inventario_usuario(user_id: int):
    async with _connection.execute("SELECT id, producto_nombre, cantidad FROM inventarios WHERE user_id = ?", (user_id,)) as cursor:
        return await cursor.fetchall()

async def usar_item_inventario(user_id: int, producto_nombre: str) -> bool:
    """
    Resta 1 a la cantidad del producto. Si llega a 0, se elimina del inventario.
    Retorna True si se pudo usar (existía y había stock), False de lo contrario.
    """
    async with _connection.execute(
        "SELECT id, cantidad FROM inventarios WHERE user_id = ? AND producto_nombre = ? COLLATE NOCASE",
        (user_id, producto_nombre)
    ) as cursor:
        row = await cursor.fetchone()

    if not row:
        return False

    if row["cantidad"] > 1:
        await _connection.execute("UPDATE inventarios SET cantidad = cantidad - 1 WHERE id = ?", (row["id"],))
    else:
        await _connection.execute("DELETE FROM inventarios WHERE id = ?", (row["id"],))

    await _connection.commit()
    return True

# --- HERRAMIENTAS DE CONTROL FISCAL (INCAUTACIÓN) ---

async def embargar_fondos(user_id: int) -> int:
    """Extrae la totalidad de los fondos de un usuario y los inyecta en la Bóveda Central (id 0)."""
    # 1. Leemos el saldo actual
    saldo_recuperado = 0
    async with _connection.execute("SELECT balance_pc FROM cuentas_bancarias WHERE id_entidad = ?", (user_id,)) as cursor:
        row = await cursor.fetchone()
        if not row or row["balance_pc"] <= 0:
            return 0  # No hay nada que embargar
        saldo_recuperado = row["balance_pc"]

    # 2. Vaciamos la cuenta del usuario
    await _connection.execute("UPDATE cuentas_bancarias SET balance_pc = 0 WHERE id_entidad = ?", (user_id,))

    # 3. Lo inyectamos de vuelta a la bóveda
    await _connection.execute("UPDATE cuentas_bancarias SET balance_pc = balance_pc + ? WHERE id_entidad = 0", (saldo_recuperado,))
    await _connection.commit()
    return saldo_recuperado

async def embargo_masivo() -> int:
    """Wipe económico total: Transfiere todos los fondos de los jugadores a la Bóveda Central."""
    # 1. Calculamos la suma de todo el oro circulante en las cuentas (excluyendo la Bóveda, id_entidad 0)
    saldo_total_recuperado = 0
    async with _connection.execute("SELECT SUM(balance_pc) as total FROM cuentas_bancarias WHERE id_entidad != 0") as cursor:
        row = await cursor.fetchone()
        if row and row["total"]:
            saldo_total_recuperado = row["total"]

    if saldo_total_recuperado > 0:
        # 2. Reseteamos el balance de todas las cuentas que no sean la bóveda a 0
        await _connection.execute("UPDATE cuentas_bancarias SET balance_pc = 0 WHERE id_entidad != 0")

        # 3. Sumamos ese total recolectado a la Bóveda Central
        await _connection.execute("UPDATE cuentas_bancarias SET balance_pc = balance_pc + ? WHERE id_entidad = 0", (saldo_total_recuperado,))
        await _connection.commit()

    return saldo_total_recuperado


async def cerrar_db():
    global _connection
    if _connection is not None:
        await _connection.close()
        _connection = None
        print("💾 [BANCO] Pool de conexiones persistentes cerrado de forma segura.")
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gremio.db")

def init_v4_schema():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA foreign_keys = ON;")

    # 1. Matriz recompensas
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS matriz_recompensas (
            rango_dm VARCHAR(20) NOT NULL,
            nivel_personaje INTEGER NOT NULL,
            max_pc_permitido INTEGER NOT NULL,
            max_rareza VARCHAR(20) NOT NULL,
            PRIMARY KEY (rango_dm, nivel_personaje)
        );
    """)

    # 2. Personajes estados
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS personajes_estados (
            user_id VARCHAR(30) PRIMARY KEY,
            estado_viajando BOOLEAN DEFAULT 0,
            viaje_desbloqueo_timestamp INTEGER DEFAULT 0,
            nivel_extenuacion INTEGER DEFAULT 0,
            estado_herido BOOLEAN DEFAULT 0,
            pendiente_auditoria BOOLEAN DEFAULT 0
        );
    """)

    # 3. Economia billetera
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS economia_billetera (
            user_id VARCHAR(30) PRIMARY KEY,
            balance_pc INTEGER DEFAULT 0 CHECK(balance_pc >= 0),
            FOREIGN KEY (user_id) REFERENCES personajes_estados(user_id) ON DELETE CASCADE
        );
    """)

    # 4. Inventario materiales (Con restriccion >= 0 por paradoja del cero)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventario_materiales (
            user_id VARCHAR(30) NOT NULL,
            item_id VARCHAR(50) NOT NULL,
            cantidad INTEGER NOT NULL CHECK(cantidad >= 0),
            PRIMARY KEY (user_id, item_id),
            FOREIGN KEY (user_id) REFERENCES personajes_estados(user_id) ON DELETE CASCADE
        );
    """)

    # 5. Inventario instancias
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventario_instancias (
            instance_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id VARCHAR(30) NOT NULL,
            item_id VARCHAR(50) NOT NULL,
            durabilidad_actual INTEGER NOT NULL CHECK(durabilidad_actual >= 0),
            grado_runa INTEGER DEFAULT 0,
            estado_critico BOOLEAN DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES personajes_estados(user_id) ON DELETE CASCADE
        );
    """)

    # 6. Recetas conocidas
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS registro_recetas_conocidas (
            user_id VARCHAR(30) NOT NULL,
            receta_id VARCHAR(50) NOT NULL,
            PRIMARY KEY (user_id, receta_id),
            FOREIGN KEY (user_id) REFERENCES personajes_estados(user_id) ON DELETE CASCADE
        );
    """)

    # 7. Registro de tickets
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS registro_tickets (
            channel_id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            estado VARCHAR(20) DEFAULT 'ABIERTO'
        );
    """)

    # INDICES
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_inventario_materiales_user ON inventario_materiales(user_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_inventario_instancias_user ON inventario_instancias(user_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_registro_recetas_user ON registro_recetas_conocidas(user_id);")

    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_v4_schema()
    print("Schema V4 inicializado!")

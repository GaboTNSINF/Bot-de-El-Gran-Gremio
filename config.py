# config.py
import os
from dotenv import load_dotenv
load_dotenv()

# --- CONFIGURACIÓN GENERAL ---
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", 1509932964056793349))

# --- CONFIGURACIÓN DE ROLES (IDs de Discord) ---
ROL_VIAJERO = 1509955739953922138
ROL_AVENTURERO = 1509955646492250122
ROL_DUNGEON_MASTER = 1509955549297381469

# --- NUEVOS RANGOS DE LICENCIA DE DUNGEON MASTERS ---
ROL_DM_APRENDIZ = 1511094617230151973
ROL_DM_EXPERTO = 1511094678064206067
ROL_DM_OFICIAL = 1511094806229684314

# --- NUEVOS TIERS DE NIVEL DE JUGADORES / AVENTUREROS ---
ROL_TIER_APRENDIZ = 1511093704658784448
ROL_TIER_AVENTURERO = 1511093928001273896
ROL_TIER_VETERANO = 1511094122822504489
ROL_TIER_HEROE = 1511094207400513737

# --- PARCHE 1: CONSTANTE DE SEGURIDAD EXCLUSIVA DE NOMINAS ---
# Solo Fundadores y Co-Fundadores pueden plantar las anclas de personal en /personal.py
ROLES_CREACION_NOMINAS = [
    1509952429586780332,  # ID Rol Fundador
    1509954249436696758   # ID Rol Co-Fundador
]

# Rangos autorizados para aprobar fichas nuevas (/aprobar_ficha)
# Según el Manifiesto: "Toda la división de la rama Gremial tiene la obligación de procesar y resolver admisiones en el chat."
ROLES_APROBACION = [
    1509955206610419914,  # ID Rol Aprendiz Gremial
    1509955203103723610,  # ID Rol Trabajador Gremial
    1509955118060142865,  # ID Rol Experto Gremial
    1509954923914203359,  # ID Rol Oficial Gremial
    1509954827822825604,  # ID Rol Supervisor Gremial
    1509954655470485645,  # ID Rol Jefe Gremial
    1509954249436696758,  # ID Rol Co-Fundador
    1509952429586780332   # ID Rol Fundador
]

# Rangos autorizados para cerrar tickets de admision y comandos basicos de gestion
ROLES_CLAUSURA = [
    1509955118060142865,  # ID Rol Experto Gremial
    1509954923914203359,  # ID Rol Oficial Gremial
    1509954827822825604,  # ID Rol Supervisor Gremial
    1509954655470485645,  # ID Rol Jefe Gremial
    1509954249436696758,  # ID Rol Co-Fundador
    1509952429586780332   # ID Rol Fundador
]

# FILTRO EXCLUSIVO: Solo la Alta Directiva y el Jefe de Área Gremial pueden alterar registros vivos de la BD (Matriculas)
ROLES_EDICION_MATRICULA = [
    1509954655470485645,  # ID Rol Jefe Gremial
    1509954249436696758,  # ID Rol Co-Fundador
    1509952429586780332   # ID Rol Fundador
]

# Incluye alta gerencia, oficiales y todo el escalafón operativo de la rama Gremial para atender Admisiones
ROLES_ACCESO_ADMISION = ROLES_APROBACION.copy()

# --- PATROCINADORES ---
ROL_PATROCINADOR = 1512293128986689606

# --- PARCHE 2: INFRAESTRUCTURA RELACIONAL DE RAMAS ADMINISTRATIVAS ---
# REQUISITO OBLIGATORIO PARA EL FUNCIONAMIENTO EN VIVO DE COGS/PERSONAL.PY
CONFIG_RAMAS = {
    "gremio": {
        "titulo": "🏛️ CONCILIO DE TRABAJADORES GREMIALES",
        "jefe_id": 1509954655470485645,  # ID Rol Jefe Gremial
        "color": 0x3498db,               # Azul
        "rangos": {
            "supervisor": 1509954827822825604,  # ID Rol Supervisor Gremial
            "oficial": 1509954923914203359,     # ID Rol Oficial Gremial
            "experto": 1509955118060142865,     # ID Rol Experto Gremial
            "trabajador": 1509955203103723610,  # ID Rol Trabajador Gremial
            "aprendiz": 1509955206610419914     # ID Rol Aprendiz Gremial
        }
    },
    "guardias": {
        "titulo": "🛡️ CUERPO DE GUARDIAS Y SEGURIDAD",
        "jefe_id": 1510094198005694594,  # ID Rol Jefe de Guardias
        "color": 0xe74c3c,               # Rojo
        "rangos": {
            "supervisor": 1512886699452141890,   # ID Rol Supervisor de Guardia
            "guardia": 1510706332385153116,      # ID Rol Guardia
            "recluta": 1512886782079795211       # ID Rol Recluta
        }
    },
    "world_building": {
        "titulo": "🔮 CARTÓGRAFOS Y ARQUITECTOS DE WORLD BUILDING",
        "jefe_id": 1509954294307098697,  # ID Rol Jefe de World Building
        "color": 0x9b59b6,               # Púrpura
        "rangos": {
            "supervisor": 1509954729449619678,   # ID Rol Supervisor de World Building
            "erudito": 1512888131408498848,      # ID Rol Erudito
            "dibujante": 1512888203529555988,    # ID Rol Dibujante
            "constructor": 1512888207891632248   # ID Rol Constructor
        }
    },
    "noticias": {
        "titulo": "📰 CRÓNICAS DEL REINO, PRENSA Y NOTICIAS",
        "jefe_id": 1509954568098938951,  # ID Rol Jefe de Noticias
        "color": 0xf1c40f,               # Amarillo
        "rangos": {
            "supervisor": 1509954824114929845,   # ID Rol Supervisor de Noticias
            "cronista": 1512890034187927684,     # ID Rol Cronista
            "periodista": 1512890068186959994,   # ID Rol Periodista
            "locutor": 1512890071672557649       # ID Rol Locutor
        }
    }
}

# --- CONFIGURACIÓN DE CATEGORÍAS (IDs de Discord) ---
CATEGORIA_PUERTA_ENTRADA = 1510010221555224747
CATEGORIA_OFICINA_COORDINACION = 1510010375498633288
CATEGORIA_MESAS_ACTIVAS = 1510010349150015498

# --- CONFIGURACIÓN DE BUZON ---
CANAL_BUZON_SECRETARIA = 1512257441218170981

# --- CANAL DE AUDITORÍA Y COORDINACIÓN DE SESIONES ---
CANAL_DISCUSION_SESIONES = 1510053136369324095

# --- CONFIGURACIÓN DE VOZ DINÁMICA ---
CANAL_HUB_VOZ = 1510698841085706383 
CATEGORIA_VOZ_TEMPORAL = 1510010349150015498
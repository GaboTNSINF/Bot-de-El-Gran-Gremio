# main.py

import asyncio
import discord
import config
from database import init_db, cerrar_db

# Configuración estricta de Intents (Permisos de red del bot)
intents = discord.Intents.default()
intents.members = True          # Para detectar nuevos usuarios y cambiar roles
intents.message_content = True  # Para leer la plantilla de texto plano en los tickets

class GremioBot(discord.Bot):
    async def on_ready(self):
        """Evento que se ejecuta cuando el bot se conecta a Discord exitosamente."""
        print(f"==========================================")
        print(f"🤖 BOT DEL GREMIO ACTIVADO EN PRODUCCIÓN")
        print(f"👤 Conectado como: {self.user.name} ({self.user.id})")
        print(f"==========================================")
        try:
            await init_db()
            print("💾 Base de datos 'gremio.db' verificada e inicializada con ruta absoluta.")
        except Exception as e:
            print(f"❌ Error Crítico al inicializar la Base de Datos: {e}")

    async def on_member_join(self, member):
        """Módulo Auto-Rol: Asigna el rol VIAJERO inmediatamente al ingresar al servidor."""
        if member.bot:
            return

        try:
            rol_viajero = member.guild.get_role(config.ROL_VIAJERO)
            if rol_viajero:
                await member.add_roles(rol_viajero)
                print(f"🦅 Rol VIAJERO asignado automáticamente a: {member.name}")
            else:
                print(f"⚠️ Error: No se encontró el ROL_VIAJERO. Verifica la ID en config.py")
        except discord.Forbidden:
            print(f"❌ Error de Permisos: El bot no tiene rango suficiente para asignar roles.")
        except Exception as e:
            print(f"❌ Error inesperado en on_member_join: {e}")

async def ejecutar_bot():
    """
    Orquesta la sesión completa del bot, carga los módulos en caliente
    y garantiza el cierre limpio de conexiones asíncronas (Discord + SQLite).
    """
    # Inicialización del Bot diferida dentro del loop activo
    # NOTA EDUCATIVA: Instanciar el bot aquí (dentro de un contexto async) es una práctica excelente.
    # Previene el clásico error de Pycord: "Future attached to a different loop" al reiniciar conexiones.
    bot = GremioBot(intents=intents, debug_guilds=[config.GUILD_ID])

    extensiones = [
        "cogs.tickets",
        "cogs.admision",
        "cogs.comunidad",
        "cogs.matchmaking",
        "cogs.voz",      
        "cogs.buzon",
        "cogs.sesiones",
        "cogs.seguridad",
        "cogs.personal",
        "cogs.economia",
        "cogs.dados", # AGREGAMOS EL NUEVO MÓDULO DE DADOS
        "cogs.tienda",  # Catálogo interactivo de items
        "cogs.taberna", # Minijuegos de apuestas con la Casa
        "cogs.botin",   # Loot tables para DMs
        "cogs.asteria_cog" # Ecosistema Asteria (Integración Reactivada)
    ]

    print("🔌 Cargando módulos del sistema de forma síncrona...")
    for ext in extensiones:
        try:
            # CORRECCIÓN SINTÁCTICA EN PYCORD: load_extension es síncrono por defecto
            bot.load_extension(ext)
            print(f"✅ Módulo '{ext}' cargado correctamente.")
        except Exception as e:
            print(f"❌ Error al cargar {ext}: {e}")

    try:
        print("🔌 Conectando con los servidores de Discord...")
        await bot.start(config.TOKEN)
    finally:
        print("\n🛑 [SISTEMA] Se ha detectado una señal de interrupción (Ctrl + C)...")
        print("🔌 Desconectando de los servidores de Discord...")

        if not bot.is_closed():
            await bot.close()

        await cerrar_db()
        print("👋 [APAGADO] Proceso finalizado de forma limpia. Bóveda resguardada.\n")


if __name__ == "__main__":
    try:
        asyncio.run(ejecutar_bot())
    except KeyboardInterrupt:
        pass
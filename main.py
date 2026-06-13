import logging
import traceback
# main.py

import asyncio
import discord
import config
from database import init_db

# Configuración estricta de Intents (Permisos de red del bot)

async def vista_global_on_error(self, error: Exception, item: discord.ui.Item, interaction: discord.Interaction):
    bot_ref = interaction.client
    error_real = getattr(error, "original", error)

    mensaje_usuario = "❌ Ha ocurrido un error interno de infraestructura al procesar este menú. El equipo técnico ha sido notificado."
    try:
        if interaction.response.is_done():
            await interaction.followup.send(mensaje_usuario, ephemeral=True)
        else:
            await interaction.response.send_message(mensaje_usuario, ephemeral=True)
    except Exception:
        pass

    componente_info = getattr(item, "custom_id", str(type(item).__name__))
    logging.error(f"Excepción en componente UI [{componente_info}]:", exc_info=error_real)

    if hasattr(bot_ref, "_despachar_alerta_telemetria"):
        await bot_ref._despachar_alerta_telemetria(
            error_real=error_real,
            contexto_origen=f"Componente UI (ID: {componente_info})",
            usuario_involucrado=interaction.user
        )

async def modal_global_on_error(self, error: Exception, interaction: discord.Interaction):
    bot_ref = interaction.client
    error_real = getattr(error, "original", error)

    mensaje_usuario = "❌ Ocurrió un error interno al procesar este formulario. El equipo técnico ha sido notificado."
    try:
        if interaction.response.is_done():
            await interaction.followup.send(mensaje_usuario, ephemeral=True)
        else:
            await interaction.response.send_message(mensaje_usuario, ephemeral=True)
    except Exception:
        pass

    logging.error(f"Excepción en componente Formulario [Modal: {type(self).__name__}]:", exc_info=error_real)

    if hasattr(bot_ref, "_despachar_alerta_telemetria"):
        await bot_ref._despachar_alerta_telemetria(
            error_real=error_real,
            contexto_origen=f"Formulario Modal ({type(self).__name__})",
            usuario_involucrado=interaction.user
        )

discord.ui.View.on_error = vista_global_on_error
discord.ui.Modal.on_error = modal_global_on_error

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


    async def _despachar_alerta_telemetria(self, error_real: Exception, contexto_origen: str, usuario_involucrado: discord.User = None):
        canal_logs = self.get_channel(config.CANAL_LOGS_ID)
        if not canal_logs:
            return

        embed = discord.Embed(
            title="⚠️ Alerta de Sistema: Excepción Capturada",
            description=f"Se ha producido un fallo durante la ejecución de: `{contexto_origen}`.",
            color=discord.Color.red()
        )
        if usuario_involucrado:
            embed.add_field(name="Usuario", value=usuario_involucrado.mention, inline=True)

        embed.add_field(name="Tipo de Error", value=f"`{type(error_real).__name__}`", inline=False)

        mensaje_error = str(error_real)
        if len(mensaje_error) > 1000:
            mensaje_error = mensaje_error[:1000] + "..."
        embed.add_field(name="Detalle", value=f"```\n{mensaje_error}\n```", inline=False)

        try:
            await canal_logs.send(embed=embed)
        except Exception as e_log:
            logging.error(f"Fallo crítico enviando telemetría a Discord: {e_log}")

    async def on_application_command_error(self, ctx: discord.ApplicationContext, error: discord.DiscordException):
        error_real = getattr(error, "original", error)

        mensaje_usuario = "❌ Ocurrió un error inesperado al procesar tu solicitud. El equipo técnico ha sido notificado."
        try:
            if ctx.response.is_done():
                await ctx.followup.send(mensaje_usuario, ephemeral=True)
            else:
                await ctx.respond(mensaje_usuario, ephemeral=True)
        except Exception:
            pass

        logging.error(f"Excepción en comando /{ctx.command.name if ctx.command else 'desconocido'}:", exc_info=error_real)
        await self._despachar_alerta_telemetria(error_real, f"Comando /{ctx.command.name if ctx.command else 'desconocido'}", ctx.user)

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
        try:
            await init_db()
            print("💾 Base de datos 'gremio.db' verificada e inicializada con ruta absoluta.")
        except Exception as e:
            print(f"❌ Error Crítico al inicializar la Base de Datos: {e}")
            import sys
            sys.exit(1)

        print("🔌 Conectando con los servidores de Discord...")
        await bot.start(config.TOKEN)
    finally:
        print("\n🛑 [SISTEMA] Se ha detectado una señal de interrupción (Ctrl + C)...")
        print("🔌 Desconectando de los servidores de Discord...")

        if not bot.is_closed():
            await bot.close()

        print("👋 [APAGADO] Proceso finalizado de forma limpia. Bóveda resguardada.\n")


if __name__ == "__main__":
    try:
        asyncio.run(ejecutar_bot())
    except KeyboardInterrupt:
        pass
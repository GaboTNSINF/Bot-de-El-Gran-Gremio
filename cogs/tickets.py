# cogs/tickets.py

import discord
from discord.ext import commands
import config
import asyncio
import re

class VistaReclamacion(discord.ui.View):
    """Componente persistente que reside dentro del canal del ticket para la gestión del Staff."""
    def __init__(self):
        # Timeout=None y sin argumentos dinámicos para garantizar persistencia absoluta post-reinicios
        super().__init__(timeout=None)

    @discord.ui.button(label="🤝 Reclamar Ticket", style=discord.ButtonStyle.success, custom_id="btn_reclamar_ticket")
    async def reclamar_callback(self, button: discord.ui.Button, interaction: discord.Interaction):
        guild = interaction.guild
        staff_miembro = interaction.user
        canal_actual = interaction.channel
        
        if not guild: 
            return

        # 1. Validación de Rango Operativo del Staff
        if not any(rol.id in config.ROLES_ACCESO_ADMISION for rol in staff_miembro.roles):
            await interaction.response.send_message("❌ No perteneces al escalafón del Gremio para reclamar este caso.", ephemeral=True)
            return

        # 2. EXTRACCIÓN DE METADATOS (Persistencia del Creador del Ticket)
        # Extraemos la ID del usuario desde el topic del canal usando expresiones regulares
        match = re.search(r"Creador:\s*(\d+)", canal_actual.topic or "")
        if not match:
            await interaction.response.send_message("❌ **Error de Integridad:** No se pudieron recuperar los metadatos de este ticket en el canal.", ephemeral=True)
            return
            
        usuario_creador_id = int(match.group(1))

        # 3. FILTRO DE INTEGRIDAD: Evitar auto-reclamos
        if staff_miembro.id == usuario_creador_id:
            await interaction.response.send_message("❌ **Control de Auditoría:** No puedes reclamar un caso abierto por ti mismo. Deja que otro miembro del gremio lo gestione.", ephemeral=True)
            return

        # 4. MITIGACIÓN DE CONDICIÓN DE CARRERA VISUAL (Filtro Mutex en Caliente)
        # Modificamos el botón INMEDIATAMENTE antes de realizar las llamadas asíncronas lentas a la API de Discord
        button.disabled = True
        button.label = f"Reclamado por {staff_miembro.name}"
        button.style = discord.ButtonStyle.secondary
        
        # Confirmamos la mutación visual de la interfaz de forma atómica
        await interaction.response.edit_message(view=self)

        # 5. OBTENCIÓN DE ENTIDADES
        usuario_creador = guild.get_member(usuario_creador_id) or await self.bot.get_or_fetch_member(guild, usuario_creador_id)

        # 6. CONSOLIDACIÓN DE LA MATRIZ DE SOBREESCRITURA DE PERMISOS
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            staff_miembro: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, read_message_history=True)
        }
        
        if usuario_creador:
            overwrites[usuario_creador] = discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, read_message_history=True)

        # Inyectar accesos de auditoría de la alta gerencia
        for rol_id in config.ROLES_CLAUSURA:
            rol = guild.get_role(rol_id)
            if rol:
                overwrites[rol] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

        # 7. Modificación Estructural de Canal (Llamada única coordinada)
        nombre_creador = usuario_creador.name if usuario_creador else f"id-{usuario_creador_id}"
        nuevo_nombre = f"⌛-{staff_miembro.name}-{nombre_creador}"
        
        try:
            await canal_actual.edit(name=nuevo_nombre, overwrites=overwrites)
        except discord.Forbidden:
            print(f"❌ Error de permisos al intentar editar el canal del ticket {canal_actual.name}")
        except discord.NotFound:
            # BLINDAJE: Si el canal fue borrado mientras alguien apretaba el botón.
            print(f"⚠️ El canal del ticket fue borrado durante la asignación.")
            return

        # 8. Notificación formal de asignación
        mencion_creador = usuario_creador.mention if usuario_creador else f"<@{usuario_creador_id}>"
        embed_asignado = discord.Embed(
            title="🤝 TICKET ASIGNADO OFICIALMENTE",
            description=f"El caso de {mencion_creador} ha sido tomado por el miembro del staff {staff_miembro.mention}.\n"
                        f"A partir de este momento, se inicia el proceso formal de revisión.",
            color=discord.Color.green()
        )
        try:
            await canal_actual.send(embed=embed_asignado)
        except discord.NotFound:
            pass # Ignoramos silenciosamente si el canal ya no existe


class TicketBotonera(discord.ui.View):
    """Componente estático que genera el botón fijo de admisión en los canales públicos."""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Abrir Ticket", style=discord.ButtonStyle.primary, custom_id="btn_abrir_ticket_admision")
    async def button_callback(self, button: discord.ui.Button, interaction: discord.Interaction):
        guild = interaction.guild
        usuario = interaction.user
        if not guild: 
            return

        categoria_id = config.CATEGORIA_PUERTA_ENTRADA
        nombre_canal = f"⌛-admision-{usuario.name}"
        mensaje_bienvenida = (
            f"👋 Saludos {usuario.mention}.\n"
            f"Has abierto tu solicitud de ingreso al Gremio. Por favor, introduce los datos "
            f"de tu personaje utilizando exactamente el formato que te proporcionarán.\n\n"
            f"⚠️ *Espere a que un trabajador del gremio inicie su proceso.*"
        )

        categoria = guild.get_channel(categoria_id)
        if not categoria:
            await interaction.response.send_message("❌ Error Crítico: Categoría destino no encontrada en config.py", ephemeral=True)
            return

        # Mapear permisos base exclusorios
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            usuario: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, read_message_history=True)
        }

        # Carga masiva de roles autorizados del Staff administrativo
        for rol_id in config.ROLES_ACCESO_ADMISION:
            rol = guild.get_role(rol_id)
            if rol:
                overwrites[rol] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

        try:
            # Diferir la respuesta inmediatamente para evitar excepciones por el handshake con la API de Discord
            await interaction.response.defer(ephemeral=True)
            
            # Crear canal inyectando la persistencia de la ID en el topic de forma explícita
            nuevo_canal = await guild.create_text_channel(
                name=nombre_canal,
                category=categoria,
                overwrites=overwrites,
                topic=f"Ticket de Admisión | Creador: {usuario.id}",
                reason=f"Ticket de admisión creado por {usuario.name}"
            )
            
            # Enviamos el mensaje inside-ticket adjuntando la vista de reclamación persistente vacía
            await nuevo_canal.send(mensaje_bienvenida, view=VistaReclamacion())
            await interaction.followup.send(f"✅ Ticket creado con éxito: {nuevo_canal.mention}", ephemeral=True)
            
        except discord.Forbidden:
            await interaction.followup.send("❌ El bot no tiene permisos suficientes para crear canales.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Ocurrió un error inesperado al procesar la admisión: {e}", ephemeral=True)


class TicketsCog(commands.Cog):
    """Módulo encargado de registrar la persistencia estática del sistema de Admisión."""
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        # Registrar ambas vistas en el administrador global del bot para asegurar la escucha pasiva infinita
        self.bot.add_view(TicketBotonera())
        self.bot.add_view(VistaReclamacion())

    @commands.slash_command(name="cerrar_ticket", description="[STAFF] Solicita la clausura manual del ticket actual.")
    async def cerrar_ticket(self, ctx: discord.ApplicationContext):
        if not any(rol.id in config.ROLES_CLAUSURA for rol in ctx.user.roles):
            await ctx.respond("❌ Exclusivo para Jefes, Supervisores y Oficiales.", ephemeral=True)
            return
        await ctx.respond("⚠️ **Solicitud de clausura iniciada.** Para destruir este canal permanentemente, escribe `/confirmar_cierre`.")

    @commands.slash_command(name="confirmar_cierre", description="[STAFF] Ejecuta la destrucción del canal del ticket actual.")
    async def confirmar_cierre(self, ctx: discord.ApplicationContext):
        if not any(rol.id in config.ROLES_CLAUSURA for rol in ctx.user.roles):
            await ctx.respond("❌ Exclusivo para Jefes, Supervisores y Oficiales.", ephemeral=True)
            return

        # Validación estructural estricta de seguridad anti-vandalismo en canales públicos
        if "admision-" in ctx.channel.name or "⌛-" in ctx.channel.name:
            # NOTA EDUCATIVA: Usamos ephemeral=False aquí para que el mensaje se mande al chat
            # del canal que está a punto de borrarse.
            await ctx.respond("🧹 Clausurando y eliminando canal en 3 segundos...")
            await asyncio.sleep(3)
            
            try:
                await ctx.channel.delete(reason=f"Clausura de ticket ejecutada por {ctx.user.name}")
            except discord.NotFound:
                pass  # Mitigar excepciones concurrentes de destrucción
            except discord.Forbidden:
                print(f"❌ Error de permisos: No se pudo eliminar el canal {ctx.channel.name} por jerarquía insuficiente.")
            except Exception as e:
                # BLINDAJE: Atrapamos cualquier otro error inesperado de red para que el bot no crashee
                print(f"⚠️ Error inesperado al intentar borrar el ticket: {e}")
        else:
            await ctx.respond("❌ Error: Este comando solo puede ser ejecutado dentro de un canal de ticket válido.", ephemeral=True)

def setup(bot):
    bot.add_cog(TicketsCog(bot))
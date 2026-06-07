# cogs/sesiones.py

import discord
from discord.ext import commands
import config
import database
import random
import asyncio

class VistaEncuestaDM(discord.ui.View):
    """Botonera interactiva e inmune a reinicios que procesa las reseñas de satisfacción."""
    def __init__(self):
        # Constructor limpio sin argumentos dinámicos para garantizar persistencia absoluta
        super().__init__(timeout=None)

    async def procesar_voto_por_contexto(self, interaction: discord.Interaction, valor: int, label_voto: str):
        """Extrae la metadata del DM desde el custom_id del botón y canaliza el voto hacia la base de datos."""
        # El custom_id viene estructurado como: "vote_tipo:dm_id"
        custom_id_raw = interaction.data["custom_id"]
        try:
            dm_id_str = custom_id_raw.split(":")[1]
            dm_id = int(dm_id_str)
        except (IndexError, ValueError):
            await interaction.response.send_message("❌ **Error de Integridad:** Los metadatos de esta encuesta están corruptos.", ephemeral=True)
            return

        # Obtener el nombre del DM desde el entorno de Discord de forma segura
        dm_usuario = interaction.client.get_user(dm_id) or await interaction.client.fetch_user(dm_id)
        dm_name = dm_usuario.name if dm_usuario else f"DM-ID-{dm_id}"

        # Transmisión asíncrona blindada hacia el backend de la BD
        await database.inyectar_fondos_ignorados(dm_id, dm_name, valor, label_voto)

        # Deshabilitar todos los componentes de la vista actual para mitigar ataques de doble votación
        for child in self.children:
            child.disabled = True
        
        await interaction.message.edit(view=self)
        await interaction.response.send_message(
            f"✅ Gracias. Tu valoración de `{label_voto}` ha sido procesada de forma anónima en el sistema.", 
            ephemeral=True
        )

    # Nota de Arquitectura: Los custom_ids se registrarán de forma dinámica en el despachador general al enviar el mensaje.
    @discord.ui.button(label="⭐ Excelencia", style=discord.ButtonStyle.success, custom_id="vote_excelencia:base")
    async def excelencia_callback(self, button: discord.ui.Button, interaction: discord.Interaction):
        await self.procesar_voto_por_contexto(interaction, 1, "Excelencia")

    @discord.ui.button(label="😐 Neutral", style=discord.ButtonStyle.secondary, custom_id="vote_neutral:base")
    async def neutral_callback(self, button: discord.ui.Button, interaction: discord.Interaction):
        await self.procesar_voto_por_contexto(interaction, 0, "Neutral")

    @discord.ui.button(label="⚠️ Alerta", style=discord.ButtonStyle.danger, custom_id="vote_alerta:base")
    async def alerta_callback(self, button: discord.ui.Button, interaction: discord.Interaction):
        await self.procesar_voto_por_contexto(interaction, -1, "Alerta")


class FormularioReporteSesion(discord.ui.Modal):
    """Formulario interactivo para procesar las crónicas y la asistencia de las mesas de campaña."""
    def __init__(self):
        super().__init__(title="📜 Reporte de Sesión de Campaña")

        self.add_item(discord.ui.InputText(label="Nombre de la Aventura", placeholder="Ej: Las Catacumbas de Ostagar", required=True))
        self.add_item(discord.ui.InputText(label="Jugadores (Separados por comas)", placeholder="Ej: gabo, ice, alistair (Usa nombres de usuario exactos)", required=True))
        self.add_item(discord.ui.InputText(label="Recompensas (Oro y Objetos)", placeholder="Ej: 50 po a cada uno", style=discord.InputTextStyle.long, required=True))
        self.add_item(discord.ui.InputText(label="Crónica Breve de la Mesa", placeholder="Resumen rápido de los acontecimientos...", style=discord.InputTextStyle.long, required=True))

    async def enviar_encuesta_individual(self, miembro, dm, aventura):
        """Corrútina interna para encapsular de forma segura el envío y evitar fallos en cascada."""
        # Instanciamos una vista limpia y modificamos los custom_ids de sus botones reflejando la ID del DM específico
        vista_personalizada = VistaEncuestaDM()
        for button in vista_personalizada.children:
            tipo_voto = button.custom_id.split(":")[0]
            button.custom_id = f"{tipo_voto}:{dm.id}"

        await miembro.send(
            f"👋 Saludos Aventurero. El **DM {dm.name}** acaba de registrar la sesión **'{aventura}'** en el Gremio.\n"
            f"Para ayudarnos a monitorear la calidad del juego, califica el desempeño de tu mesa:",
            view=vista_personalizada
        )

    async def callback(self, interaction: discord.Interaction):
        # Handshake inmediato para mitigar de raíz el error 10062 de expiración de la API de Discord
        await interaction.response.defer(ephemeral=True)
        
        guild = interaction.guild
        dm = interaction.user
        if not guild: 
            return

        canal_auditoria = guild.get_channel(config.CANAL_DISCUSION_SESIONES)
        if not canal_auditoria:
            await interaction.followup.send("❌ Error: Canal de discusión de sesiones inaccesible. Verifica la ID en config.py.", ephemeral=True)
            return

        aventura = self.children[0].value.strip()
        jugadores_raw = self.children[1].value.strip().split(",")
        recompensas = self.children[2].value.strip()
        cronica = self.children[3].value.strip()

        miembros_detectados = []
        menciones_texto = []
        
        # PROCESAMIENTO OPTIMIZADO EXCLUSIVO: Indexación O(N) local para búsquedas O(1)
        # Reemplazamos guild.get_member_named() (que en pycord hace un escaneo lineal O(N) oculto por cada jugador)
        # por un mapa local de hash generado en una sola pasada. (Optimización de Bolt ⚡)
        mapa_miembros = None

        for p_name in jugadores_raw:
            p_name = p_name.strip()
            if not p_name: 
                continue
            
            member = None
            # Intento de resolución 1: ID numérica directa (Hachazo rápido al caché de memoria)
            if p_name.isdigit():
                member = guild.get_member(int(p_name))
            
            # Intento de resolución 2: Búsqueda O(1) nativa local
            if not member:
                if mapa_miembros is None:
                    # Lazy loading: Solo construimos el índice O(N) si alguien usa un nombre en lugar de ID
                    mapa_miembros = {}
                    for m in guild.members:
                        mapa_miembros[m.name.lower()] = m
                        if hasattr(m, 'global_name') and m.global_name:
                            mapa_miembros[m.global_name.lower()] = m
                        if m.nick:
                            mapa_miembros[m.nick.lower()] = m

                member = mapa_miembros.get(p_name.lower())

            if member:
                miembros_detectados.append(member)
                menciones_texto.append(member.mention)
            else:
                menciones_texto.append(f"`{p_name}` (No encontrado)")

        folio = random.randint(10000, 99999)

        # Generar tarjeta de auditoría analítica
        embed_auditoria = discord.Embed(title=f"🗃️ AUDITORÍA DE SESIÓN • FOLIO #{folio}", color=discord.Color.gold())
        embed_auditoria.add_field(name="👑 Dungeon Master", value=dm.mention, inline=True)
        embed_auditoria.add_field(name="⚔️ Aventura", value=aventura, inline=True)
        embed_auditoria.add_field(name="👥 Jugadores En la Mesa", value=", ".join(menciones_texto), inline=False)
        embed_auditoria.add_field(name="💰 Recompensas Declaradas", value=recompensas, inline=False)
        embed_auditoria.add_field(name="📖 Bitácora del Narrador", value=cronica, inline=False)
        embed_auditoria.set_footer(text="Filtro de Calidad • Encuestas de feedback inmediato.")

        await canal_auditoria.send(embed=embed_auditoria)

        # DISPARO ASÍNCRONO CONCURRENTE SENIOR: Procesamiento en paralelo mediante orquestación de corrutinas
        # Esto evita cuellos de botella secuenciales si un usuario tiene DMs cerrados o lag de conexión
        tareas = []
        for miembro in miembros_detectados:
            if miembro.bot: 
                continue
            tareas.append(self.enviar_encuesta_individual(miembro, dm, aventura))

        # Ejecución masiva controlada en paralelo (Ignora errores de usuarios con DMs cerrados para evitar crasheos)
        resultados = await asyncio.gather(*tareas, return_exceptions=True)
        votos_enviados = sum(1 for res in resultados if not isinstance(res, Exception))

        await interaction.followup.send(
            f"✅ **Reporte Recibido (Folio #{folio}):** Datos asentados en el canal de coordinación.\n"
            f"Se han disparado `{votos_enviados}` encuestas automáticas de satisfacción a los jugadores en paralelo.",
            ephemeral=True
        )


class SesionesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        # Inyectar la vista estática base en el despachador de Pycord para asegurar la persistencia infinita tras apagados
        self.bot.add_view(VistaEncuestaDM())

    @commands.slash_command(name="reportar_sesion", description="[DM] Despliega el formulario oficial para asentar los datos de tu última partida.")
    async def reportar_sesion(self, ctx: discord.ApplicationContext):
        if not any(rol.id == config.ROL_DUNGEON_MASTER for rol in ctx.user.roles):
            await ctx.respond("❌ Solo los miembros con el rol oficial de Dungeon Master pueden firmar actas de sesión.", ephemeral=True)
            return
        await ctx.send_modal(FormularioReporteSesion())

    @commands.slash_command(name="auditar_dm", description="[STAFF] Extrae el análisis estadístico del Score Neto de un Dungeon Master.")
    async def auditar_dm(self, ctx: discord.ApplicationContext, dm_usuario: discord.Member):
        if not any(rol.id in config.ROLES_CLAUSURA for rol in ctx.user.roles):
            await ctx.respond("❌ Comando exclusivo para el alto mando de la Directiva.", ephemeral=True)
            return

        # El nuevo database.py ya resuelve el perfil y las reseñas agrupadas en una única consulta indexada ultrarrápida
        dm_perfil = await database.obtener_perfil_dm(dm_usuario.id)

        if not dm_perfil or dm_perfil["partidas"] == 0:
            await ctx.respond(f"ℹ️ El usuario {dm_usuario.mention} no registra actividad de narración activa en la base de datos.", ephemeral=True)
            return

        embed = discord.Embed(title=f"📊 CUADRO DE MANDO ANALÍTICO: {dm_usuario.name}", color=discord.Color.dark_teal())
        embed.add_field(name="🛡️ Licencia Actual", value=f"`{dm_perfil['licencia']}`", inline=True)
        embed.add_field(name="🎲 Sesiones Registradas", value=f"`{dm_perfil['partidas']} partidas`", inline=True)
        embed.add_field(name="📬 Muestreo de Reseñas", value=f"`{dm_perfil['total_validas']} individuales`", inline=True)
        embed.add_field(name="📈 Índice de Aprobación", value=f"**{dm_perfil['aprobacion']:.1f}%**", inline=True)

        if dm_perfil["aprobacion"] >= 75.0:
            embed.description = "💡 **Dictamen del Sistema:** Salud de mesa óptima. El DM cuenta con aprobación mayoritaria del gremio."
        else:
            embed.description = "⚠️ **Dictamen del Sistema:** Alerta de calidad. El índice de aprobación se encuentra por debajo del estándar sugerido."

        await ctx.respond(embed=embed)

def setup(bot):
    bot.add_cog(SesionesCog(bot))
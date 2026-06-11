# cogs/sesiones.py

import discord
from discord.ext import commands
import config
import database
import random
import asyncio
import re

class VistaEncuestaDM(discord.ui.View):
    """Botonera interactiva que procesa las reseñas de satisfacción."""
    def __init__(self):
        super().__init__(timeout=None)

    async def procesar_voto_por_contexto(self, interaction: discord.Interaction, valor: int, label_voto: str):
        try:
            if not interaction.message.embeds or not interaction.message.embeds[0].footer or not interaction.message.embeds[0].footer.text:
                raise ValueError("Embed o footer faltante")

            footer_text = interaction.message.embeds[0].footer.text
            match = re.search(r"DM-ID:\s*(\d+)", footer_text)
            if not match:
                raise ValueError("Formato de DM-ID no encontrado")

            dm_id = int(match.group(1))
        except (IndexError, ValueError, AttributeError):
            await interaction.response.send_message("❌ **Error de Integridad:** Los metadatos de esta encuesta están corruptos.", ephemeral=True)
            return

        dm_usuario = interaction.client.get_user(dm_id) or await interaction.client.fetch_user(dm_id)
        dm_name = dm_usuario.name if dm_usuario else f"DM-ID-{dm_id}"

        await database.inyectar_fondos_ignorados(dm_id, dm_name, valor, label_voto)

        for child in self.children:
            child.disabled = True
        
        await interaction.message.edit(view=self)
        await interaction.response.send_message("✅ Voto registrado. Gracias por tu feedback.", ephemeral=True)

    @discord.ui.button(label="Excelente (5/5)", style=discord.ButtonStyle.success, custom_id="vote_exc")
    async def btn_exc(self, button: discord.ui.Button, interaction: discord.Interaction):
        await self.procesar_voto_por_contexto(interaction, 5, "Excelente")

    @discord.ui.button(label="Bueno (4/5)", style=discord.ButtonStyle.primary, custom_id="vote_bueno")
    async def btn_bueno(self, button: discord.ui.Button, interaction: discord.Interaction):
        await self.procesar_voto_por_contexto(interaction, 4, "Bueno")

    @discord.ui.button(label="Regular (3/5)", style=discord.ButtonStyle.secondary, custom_id="vote_reg")
    async def btn_reg(self, button: discord.ui.Button, interaction: discord.Interaction):
        await self.procesar_voto_por_contexto(interaction, 3, "Regular")

    @discord.ui.button(label="Malo (1/5)", style=discord.ButtonStyle.danger, custom_id="vote_malo")
    async def btn_malo(self, button: discord.ui.Button, interaction: discord.Interaction):
        await self.procesar_voto_por_contexto(interaction, 1, "Malo")

async def enviar_encuesta_individual(miembro, dm, aventura):
    vista_personalizada = VistaEncuestaDM()

    embed = discord.Embed(
        title="Evaluación de Sesión",
        description=f"👋 Saludos Aventurero. El **DM {dm.name}** acaba de registrar la sesión **'{aventura}'** en el Gremio.\n"
                    f"Para ayudarnos a monitorear la calidad del juego, califica el desempeño de tu mesa:",
        color=discord.Color.blue()
    )
    embed.set_footer(text=f"DM-ID:{dm.id}")

    try:
        await miembro.send(embed=embed, view=vista_personalizada)
    except discord.Forbidden:
        pass

class ModalRecompensasGlobales(discord.ui.Modal):
    def __init__(self, jugadores, salvaciones):
        super().__init__(title="Recompensas y Variables Globales")
        self.jugadores = jugadores
        self.salvaciones = salvaciones

        self.add_item(discord.ui.InputText(label="Aventura / Crónica Breve", placeholder="El asalto a la fortaleza...", required=True))
        self.add_item(discord.ui.InputText(label="PC Totales a repartir por jugador", placeholder="Ej: 50000", required=True))
        self.add_item(discord.ui.InputText(label="ID Objeto Recompensa (Opcional)", placeholder="Ej: pocion_curacion", required=False))
        self.add_item(discord.ui.InputText(label="ID Anillo Geográfico de Viaje", placeholder="Ej: 2", required=True))

    async def callback(self, interaction: discord.Interaction):
        interaccion_expirada = False
        try:
            await interaction.response.defer(ephemeral=True)
        except discord.NotFound:
            interaccion_expirada = True

        aventura = self.children[0].value.strip()

        try:
            pc_totales = int(self.children[1].value.strip())
        except ValueError:
            await interaction.followup.send("❌ El valor de PC Totales debe ser un número entero.", ephemeral=True)
            return

        objeto_id = self.children[2].value.strip()

        try:
            anillo_id = int(self.children[3].value.strip())
        except ValueError:
            await interaction.followup.send("❌ El ID del Anillo Geográfico debe ser un número entero válido.", ephemeral=True)
            return

        obj_norm = None
        if objeto_id:
            obj_norm = re.sub(r'[\s]+', '_', objeto_id).lower()

        # Inyección Atómica Principal
        async with database.db_lock:
            try:
                await database._connection.execute("BEGIN")
                for j in self.jugadores:
                    j_id = int(j.id)
                    await database._connection.execute("INSERT OR IGNORE INTO personajes_estados (user_id) VALUES (?)", (j_id,))

                    extenuacion_mod = 0 if self.salvaciones.get(j.id, True) else 1

                    await database._connection.execute("""
                        UPDATE personajes_estados
                        SET estado_viajando = 1,
                            nivel_extenuacion = nivel_extenuacion + ?,
                            anillo_geografico_id = ?
                        WHERE user_id = ?
                    """, (extenuacion_mod, anillo_id, j_id))

                    await database._connection.execute("INSERT OR IGNORE INTO economia_billetera (user_id, balance_pc) VALUES (?, 0)", (j_id,))
                    await database._connection.execute("UPDATE economia_billetera SET balance_pc = balance_pc + ? WHERE user_id = ?", (pc_totales, j_id))

                    if obj_norm:
                        await database._connection.execute("INSERT OR IGNORE INTO inventario_materiales (user_id, item_id, cantidad) VALUES (?, ?, 0)", (j_id, obj_norm))
                        await database._connection.execute("UPDATE inventario_materiales SET cantidad = cantidad + 1 WHERE user_id = ? AND item_id = ?", (j_id, obj_norm))
                await database._connection.commit()
            except Exception as e:
                await database._connection.rollback()
                await interaction.followup.send(f"❌ Error de base de datos durante la inyección atómica: {e}", ephemeral=True)
                return

        # Generar tarjeta de auditoría
        folio = random.randint(10000, 99999)
        canal_auditoria = interaction.guild.get_channel(config.CANAL_DISCUSION_SESIONES)
        menciones_texto = [j.mention for j in self.jugadores]

        embed_auditoria = discord.Embed(title=f"🗃️ AUDITORÍA DE SESIÓN • FOLIO #{folio}", color=discord.Color.gold())
        embed_auditoria.add_field(name="👑 Dungeon Master", value=interaction.user.mention, inline=True)
        embed_auditoria.add_field(name="⚔️ Aventura", value=aventura, inline=True)
        embed_auditoria.add_field(name="💍 Anillo de Viaje", value=f"ID: {anillo_id}", inline=True)
        embed_auditoria.add_field(name="👥 Jugadores En la Mesa", value=", ".join(menciones_texto), inline=False)
        embed_auditoria.add_field(name="💰 PC Otorgados", value=f"{pc_totales} a c/u", inline=True)
        embed_auditoria.add_field(name="🛡️ Fallaron Salvación", value=str(sum(1 for v in self.salvaciones.values() if not v)), inline=True)

        auditoria_exitosa = False
        if canal_auditoria:
            try:
                await canal_auditoria.send(embed=embed_auditoria)
                auditoria_exitosa = True
            except discord.HTTPException as e:
                print(f"⚠️ Error de red al enviar auditoría: {e}")

        # FLUJO DE CONTINGENCIA BLINDADO (Lock encapsulando try...except y mapeo relacional Padre-Hijo completo)
        if not auditoria_exitosa:
            import time
            timestamp = int(time.time())
            async with database.db_lock:
                try:
                    await database._connection.execute("BEGIN")
                    async with database._connection.execute(
                        "INSERT INTO auditoria_sesiones_fallidas (folio, dm_id, timestamp, aventura, recompensa_pc, recompensa_objeto) VALUES (?, ?, ?, ?, ?, ?)",
                        (folio, interaction.user.id, timestamp, aventura, pc_totales, obj_norm)
                    ) as cursor:
                        auditoria_id = cursor.lastrowid

                    for j in self.jugadores:
                        await database._connection.execute(
                            "INSERT INTO auditoria_sesiones_jugadores (auditoria_id, user_id) VALUES (?, ?)",
                            (auditoria_id, int(j.id))
                        )
                    await database._connection.commit()
                except Exception as e:
                    await database._connection.rollback()
                    print(f"⚠️ Error fatal al guardar la auditoría histórica del folio #{folio}: {e}")

        tareas = [enviar_encuesta_individual(j, interaction.user, aventura) for j in self.jugadores if not j.bot]
        await asyncio.gather(*tareas, return_exceptions=True)

        if auditoria_exitosa:
            mensaje_exito = f"✅ **Reporte Exitoso (Folio #{folio}):** Datos inyectados atómicamente en la DB."
        else:
            mensaje_exito = f"⚠️ Recompensas inyectadas, pero falló la conexión con el canal de auditoría. Tu folio ha sido respaldado de manera local. Por favor, proporciona el **Folio #{folio}** a la administración."

        if not interaccion_expirada:
            await interaction.followup.send(mensaje_exito, ephemeral=True)
        else:
            try:
                await interaction.user.send(f"⚠️ La interacción expiró pero rescatamos los datos.\n{mensaje_exito}")
            except:
                pass

class VistaSalvaciones(discord.ui.View):
    def __init__(self, jugadores):
        super().__init__(timeout=900)
        self.jugadores = jugadores
        self.salvaciones = {j.id: True for j in jugadores}

        opciones = [discord.SelectOption(label=j.display_name, value=str(j.id)) for j in jugadores]
        self.select = discord.ui.Select(placeholder="¿Quiénes fallaron la tirada de Constitución?", min_values=0, max_values=len(opciones), options=opciones)
        self.select.callback = self.select_callback
        self.add_item(self.select)

        btn_confirmar = discord.ui.Button(label="Proceder al Modal Global", style=discord.ButtonStyle.success, row=1)
        btn_confirmar.callback = self.confirmar_callback
        self.add_item(btn_confirmar)

    async def select_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.salvaciones = {j.id: True for j in self.jugadores}
        for val in self.select.values:
            self.salvaciones[int(val)] = False

    async def confirmar_callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ModalRecompensasGlobales(self.jugadores, self.salvaciones))

class VistaSeleccionJugadores(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=900)
        self.user_select = discord.ui.UserSelect(placeholder="Selecciona a los jugadores de tu mesa (Max 8)", min_values=1, max_values=8)
        self.user_select.callback = self.user_select_callback
        self.add_item(self.user_select)

    async def user_select_callback(self, interaction: discord.Interaction):
        jugadores = self.user_select.values
        if not jugadores:
            await interaction.response.send_message("❌ Debes seleccionar al menos un jugador.", ephemeral=True)
            return
        await interaction.response.edit_message(content="**Paso 2:** Selecciona a los jugadores que *FALLARON* su salvación de Constitución por el viaje/extenuación.", view=VistaSalvaciones(jugadores))

class SesionesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(VistaEncuestaDM())

    @commands.slash_command(name="reportar_sesion", description="[DM] Despliega el flujo oficial para asentar los datos de tu última partida.")
    async def reportar_sesion(self, ctx: discord.ApplicationContext):
        if not any(rol.id == config.ROL_DUNGEON_MASTER for rol in ctx.user.roles):
            await ctx.respond("❌ Solo los miembros con el rol oficial de Dungeon Master pueden firmar actas de sesión.", ephemeral=True)
            return
        await ctx.respond("**Paso 1:** Selecciona los miembros de Discord que participaron en la sesión.", view=VistaSeleccionJugadores(), ephemeral=True)

    @commands.slash_command(name="auditar_dm", description="[STAFF] Extrae el análisis estadístico del Score Neto de un Dungeon Master.")
    async def auditar_dm(self, ctx: discord.ApplicationContext, dm_usuario: discord.Member):
        if not any(rol.id in config.ROLES_CLAUSURA for rol in ctx.user.roles):
            await ctx.respond("❌ Comando exclusivo para el alto mando de la Directiva.", ephemeral=True)
            return

        dm_perfil = await database.obtener_perfil_dm(dm_usuario.id)
        if not dm_perfil or dm_perfil["partidas"] == 0:
            await ctx.respond(f"ℹ️ El usuario {dm_usuario.mention} no registra actividad de narración activa.", ephemeral=True)
            return

        embed = discord.Embed(title=f"📊 CUADRO DE MANDO ANALÍTICO: {dm_usuario.name}", color=discord.Color.dark_teal())
        embed.add_field(name="🛡️ Licencia Actual", value=f"`{dm_perfil['licencia']}`", inline=True)
        embed.add_field(name="🎲 Sesiones Registradas", value=f"`{dm_perfil['partidas']} partidas`", inline=True)
        embed.add_field(name="📬 Muestreo de Reseñas", value=f"`{dm_perfil['total_validas']} individuales`", inline=True)
        embed.add_field(name="📈 Índice de Aprobación", value=f"**{dm_perfil['aprobacion']:.1f}%**", inline=True)

        if dm_perfil["aprobacion"] >= 75.0:
            embed.description = "💡 **Dictamen del Sistema:** Salud de mesa óptima. El DM cuenta con aprobación mayoritaria."
        else:
            embed.description = "⚠️ **Dictamen del Sistema:** Alerta de calidad. El índice de aprobación está por debajo del estándar."

        await ctx.respond(embed=embed)

def setup(bot):
    bot.add_cog(SesionesCog(bot))

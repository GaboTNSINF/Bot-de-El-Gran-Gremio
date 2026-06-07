# cogs/matchmaking.py

import discord
from discord.ext import commands
import config
import database
import asyncio
import re
from itertools import combinations

class SelectorRolHibrido(discord.ui.View):
    """Aparece por DM solo si el usuario posee simultáneamente los roles de Aventurero y DM."""
    def __init__(self, cog, miembro):
        super().__init__(timeout=180)
        self.cog = cog
        self.miembro = miembro

    @discord.ui.button(label="⚔️ Buscar como Aventurero", style=discord.ButtonStyle.primary)
    async def como_jugador(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_message("Has seleccionado la cola de **Aventureros**. Iniciando asistente...", ephemeral=True)
        self.stop()
        await self.cog.iniciar_asistente_config(interaction.user, self.miembro, "jugador")

    @discord.ui.button(label="📜 Buscar como Dungeon Master", style=discord.ButtonStyle.success)
    async def como_dm(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_message("Has seleccionado la cola de **Dungeon Masters**. Iniciando asistente...", ephemeral=True)
        self.stop()
        await self.cog.iniciar_asistente_config(interaction.user, self.miembro, "dm")


class FormularioHorarioModal(discord.ui.Modal):
    """Formulario interactivo para procesar horas libres y quórum del DM mediante análisis sintáctico."""
    def __init__(self, cog, miembro, rol_busqueda, zona_horaria, nivel_usuario):
        super().__init__(title="⏰ Configura tu Rango de Tiempo")
        self.cog = cog
        self.miembro = miembro
        self.rol_busqueda = rol_busqueda
        self.zona_horaria = zona_horaria
        self.nivel_usuario = nivel_usuario

        self.add_item(discord.ui.InputText(
            label="Días libres (Lunes a Domingo)",
            placeholder="Ej: Lunes, Miercoles, Viernes o todos",
            required=True,
            max_length=50
        ))

        self.add_item(discord.ui.InputText(
            label="Rango de Horas en tu formato local (24h)",
            placeholder="Ej: 18:00 a 22:00 o 14:30 - 20:00",
            required=True,
            max_length=30
        ))

        if self.rol_busqueda == "dm":
            self.add_item(discord.ui.InputText(
                label="Cantidad de jugadores deseada (Mín 3, Máx 5)",
                placeholder="Escribe un número entero: 3, 4 o 5",
                required=True,
                max_length=1
            ))

    async def callback(self, interaction: discord.Interaction):
        # El defer ocurre INMEDIATAMENTE para congelar el token de la interacción y evitar expiraciones por lag
        await interaction.response.defer(ephemeral=True)
        
        dias_texto = self.children[0].value.strip()
        horas_raw = self.children[1].value.strip()
        limite_jugadores = 4  # Contingencia estándar

        if self.rol_busqueda == "dm":
            limite_raw = self.children[2].value.strip()
            if not limite_raw.isdigit() or not (3 <= int(limite_raw) <= 5):
                await interaction.followup.send("❌ **Error de quórum:** Tu mesa debe ser estrictamente para 3, 4 o 5 jugadores.", ephemeral=True)
                return
            limite_jugadores = int(limite_raw)

        # Motor Regex estricto
        patron = r"(\d{1,2}):(\d{2})\s*(?:a|-)\s*(\d{1,2}):(\d{2})"
        match = re.search(patron, horas_raw)
        
        if not match:
            await interaction.followup.send("❌ **Formato inválido:** Usa una estructura normalizada como: `18:00 a 22:00`.", ephemeral=True)
            return

        h_ini, m_ini, h_fin, m_fin = map(int, match.groups())
        if h_ini >= 24 or h_fin >= 24 or m_ini >= 60 or m_fin >= 60:
            await interaction.followup.send("❌ **Error cronológico:** Valores fuera de los límites de un reloj real de 24 horas.", ephemeral=True)
            return

        # Conversión escalar a minutos absolutos
        minutos_inicio_local = h_ini * 60 + m_ini
        minutos_fin_local = h_fin * 60 + m_fin

        if minutos_fin_local <= minutos_inicio_local:
            minutos_fin_local += 24 * 60 

        # Normalización matemática exacta a huso UTC-0
        desfase_minutos = self.zona_horaria * 60
        inicio_utc = (minutos_inicio_local - desfase_minutos) % (24 * 60)
        fin_utc = (minutos_fin_local - desfase_minutos) % (24 * 60)

        if fin_utc <= inicio_utc:
            fin_utc += 24 * 60

        # Tipado fuerte e inyección limpia en la base de datos
        tier_juego = str(limite_jugadores) if self.rol_busqueda == "dm" else str(self.nivel_usuario)
        await database.guardar_registro_matchmaking(
            self.miembro.id, self.rol_busqueda, tier_juego, dias_texto, inicio_utc, fin_utc
        )

        await interaction.followup.send(
            f"💾 **CONEXIÓN COMPATIBLE ESTABLECIDA:** Tu configuración ha sido registrada en UTC-0.\n"
            f"• **Días:** `{dias_texto}`\n"
            f"• **Huso Horario:** `GMT{self.zona_horaria:+}`\n"
            f"• **Filtro:** `{limite_jugadores if self.rol_busqueda == 'dm' else f'Nivel {self.nivel_usuario}'}`\n"
            f"Ya puedes invocar `/buscar_grupo` en el servidor.", 
            ephemeral=True
        )


class VistaSelectorZonaPaises(discord.ui.View):
    """Menú desplegable de husos horarios locales."""
    def __init__(self, cog, miembro, rol_busqueda, nivel_usuario):
        super().__init__(timeout=300)
        self.cog = cog
        self.miembro = miembro
        self.rol_busqueda = rol_busqueda
        self.nivel_usuario = nivel_usuario

    @discord.ui.select(
        placeholder="🌐 Selecciona tu País o Huso Horario Local",
        options=[
            discord.SelectOption(label="España Continental / Madrid (GMT+2)", value="es_2"),
            discord.SelectOption(label="Islas Canarias (GMT+1)", value="canarias_1"),
            discord.SelectOption(label="Argentina / Uruguay / Brasil (GMT-3)", value="arg_3"),
            discord.SelectOption(label="Chile Continental (GMT-4)", value="cl_4"),
            discord.SelectOption(label="Bolivia / Paraguay / Venezuela (GMT-4)", value="ven_4"),
            discord.SelectOption(label="Perú / Colombia / Ecuador / Panamá (GMT-5)", value="per_5"),
            discord.SelectOption(label="México Centro / Costa Rica / Honduras (GMT-6)", value="mex_6")
        ]
    )
    async def select_pais(self, select: discord.ui.Select, interaction: discord.Interaction):
        id_zona_raw = interaction.data["values"][0]
        mapeo_gmt = {
            "es_2": 2, "canarias_1": 1, "arg_3": -3, "cl_4": -4,
            "ven_4": -4, "per_5": -5, "mex_6": -6
        }
        zona_elegida = mapeo_gmt.get(id_zona_raw, -4)
        
        await interaction.response.send_modal(FormularioHorarioModal(
            self.cog, self.miembro, self.rol_busqueda, zona_elegida, self.nivel_usuario
        ))
        self.stop()


class MatchmakingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="matchmaking", description="Configura tus datos de juego de forma privada por DM.")
    async def matchmaking(self, ctx: discord.ApplicationContext):
        miembro = ctx.user
        tiene_aventurero = any(rol.id == config.ROL_AVENTURERO for rol in miembro.roles)
        tiene_dm = any(rol.id == config.ROL_DUNGEON_MASTER for rol in miembro.roles)

        if not tiene_aventurero and not tiene_dm:
            await ctx.respond("❌ Debes poseer el rol de Aventurero o Dungeon Master para acceder al emparejamiento.", ephemeral=True)
            return

        await ctx.respond("📬 He abierto un asistente de configuración en tus Mensajes Directos (DM).", ephemeral=True)

        if tiene_aventurero and tiene_dm:
            view = SelectorRolHibrido(self, miembro)
            await miembro.send("⚔️ **SISTEMA DE EMPAREJAMIENTO**\nDetecté que tienes ambos roles. ¿En qué modalidad deseas buscar partida?", view=view)
        elif tiene_dm:
            await self.iniciar_asistente_config(miembro, miembro, "dm")
        else:
            await self.iniciar_asistente_config(miembro, miembro, "jugador")

    async def iniciar_asistente_config(self, usuario_dm, miembro_guild, rol_busqueda):
        nivel_final = 1
        if rol_busqueda == "jugador":
            ficha = await database.obtener_personaje(miembro_guild.id)
            if not ficha:
                await usuario_dm.send("❌ Error: Tu ficha no está registrada en los libros oficiales del gremio.")
                return
            nivel_final = ficha["nivel"] # Uso seguro gracias a Row Factory
            await usuario_dm.send(f"🏷️ **Detección Automática de Nivel:** Registrado como **Nivel {nivel_final}**.")

        view = VistaSelectorZonaPaises(self, miembro_guild, rol_busqueda, nivel_final)
        await usuario_dm.send("Por favor, selecciona tu zona horaria para calibrar el motor de conversión:", view=view)

    @commands.slash_command(name="buscar_grupo", description="Inicia el rastreo síncrono en la cola activa de búsqueda.")
    async def buscar_grupo(self, ctx: discord.ApplicationContext):
        await ctx.respond("⚡ **Iniciando rastreo de compatibilidad relacional en base de datos...**")
        await self.ejecutar_algoritmo_matchmaking(ctx.guild)

    @commands.slash_command(name="finalizar_busqueda", description="Te retira de forma inmediata de la cola de búsqueda.")
    async def finalizar_busqueda(self, ctx: discord.ApplicationContext):
        exito = await database.eliminar_de_cola(ctx.user.id)
        if exito:
            await ctx.respond("🧹 Retirado de la cola de búsqueda de forma exitosa.")
        else:
            await ctx.respond("❌ No te encuentras en ninguna cola activa.", ephemeral=True)

    def verificar_balance_grupo(self, grupo_candidato):
        """Valida matemáticamente las dos restricciones obligatorias de balanceo del gremio."""
        # grupo_candidato: [(j_id, j_nivel, j_inicio, j_fin), ...]
        niveles = [jugador[1] for jugador in grupo_candidato]
        
        # REGLA 1: Aislamiento estricto del Bloque de Aprendizaje (Nivel 1 y 2)
        if any(n in [1, 2] for n in niveles):
            return all(n in [1, 2] for n in niveles)
            
        # REGLA 2: Brecha móvil tolerante para niveles >= 3 (Diferencia máxima de ±2)
        return (max(niveles) - min(niveles)) <= 2

    async def ejecutar_algoritmo_matchmaking(self, guild):
        """Algoritmo de Ventana Desplazable optimizado mediante pre-filtrado SQL."""
        cola = await database.obtener_toda_la_cola()
        dms = [u for u in cola if u["rol_busqueda"] == "dm"]

        for dm in dms:
            dm_id = dm["user_id"]
            quorum_objetivo = int(dm["tier_juego"]) if dm["tier_juego"].isdigit() else 4
            
            # EJECUCIÓN INDUSTRIAL: SQLite hace todo el trabajo de tiempo; Python recibe datos limpios [cite: 1, 2, 3]
            candidatos = await database.obtener_candidatos_compatibles_dm(dm_id, quorum_objetivo)
            
            if len(candidatos) < quorum_objetivo:
                continue  # Quórum insuficiente de tiempo compatible

            # Convertir filas a tuplas manejables para combinatoria limpia
            lista_limpia = [(c["user_id"], c["nivel"], c["hora_inicio_utc"], c["hora_fin_utc"]) for c in candidatos]
            mesa_consolidada = None
            
            # La combinatoria se ejecuta en un conjunto drásticamente reducido (Cero congelamientos de CPU)
            for combinacion in combinations(lista_limpia, quorum_objetivo):
                if self.verificar_balance_grupo(combinacion):
                    mesa_consolidada = combinacion
                    break

            if mesa_consolidada:
                grupo_final_ids = [item[0] for item in mesa_consolidada]
                categoria = guild.get_channel(config.CATEGORIA_MESAS_ACTIVAS)
                if not categoria: 
                    return

                overwrites = {guild.default_role: discord.PermissionOverwrite(view_channel=False)}
                dm_user = guild.get_member(dm_id)
                if dm_user: 
                    overwrites[dm_user] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

                detalles_niveles = []
                for jugador_final in mesa_consolidada:
                    j_id, j_nv, _, _ = jugador_final
                    detalles_niveles.append(f"<@{j_id}> (Nivel {j_nv})")
                    j_user = guild.get_member(j_id)
                    if j_user: 
                        overwrites[j_user] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

                for rol_id in config.ROLES_CLAUSURA:
                    rol = guild.get_role(rol_id)
                    if rol: 
                        overwrites[rol] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

                nuevo_canal = await guild.create_text_channel(
                    name=f"⚔-mesa-dm-{dm_user.name.lower() if dm_user else 'anon'}"[:100],
                    category=categoria,
                    overwrites=overwrites
                )

                mensaje = (
                    f"⚔️ **¡MESA GREMIAL CONSOLIDADA EXITOSAMENTE!**\n\n"
                    f"**Dungeon Master Asignado:** <@{dm_id}>\n"
                    f"**Aventureros Confirmados ({len(grupo_final_ids)}/{quorum_objetivo}):**\n"
                    f"• " + "\n• ".join(detalles_niveles) + "\n\n"
                    rf"⚙️ *Nota de Balance:* El grupo cumple con la tolerancia de niveles móviles (2) \n"
                    f"Mención de control: <@&{config.ROLES_CLAUSURA[0]}>."
                )
                await nuevo_canal.send(mensaje)

                # Limpieza de cola inmediata
                await database.eliminar_de_cola(dm_id)
                for j_id in grupo_final_ids:
                    await database.eliminar_de_cola(j_id)
                return 

def setup(bot):
    bot.add_cog(MatchmakingCog(bot))
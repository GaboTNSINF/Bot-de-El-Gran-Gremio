# cogs/personal.py

import discord
from discord.ext import commands
import config
import database

# ID del canal de logs donde el bot registrará la auditoría de personal
CANAL_LOGS_ID = 1513250885730570442

class PersonalCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # 👑 SECCIÓN: COMANDOS DE INICIALIZACIÓN (EXCLUSIVOS DEL FUNDADOR)

    async def _desplegar_ancla_base(self, ctx: discord.ApplicationContext, key_rama: str):
        """Función interna para clavar o resetear los Embeds fijos en el canal PERSONAL."""
        if not any(rol.id in config.ROLES_CREACION_NOMINAS for rol in ctx.user.roles):
            await ctx.respond("❌ **Acceso Denegado:** Solo la Alta Directiva Suprema posee las llaves de la Tesorería.", ephemeral=True)
            return

        rama = config.CONFIG_RAMAS[key_rama]
        embed = discord.Embed(
            title=rama["titulo"],
            description="*Inicializando registro de nómina...*",
            color=rama["color"]
        )
        embed.set_footer(text="Registro de Nómina Oficial — Actualizado en vivo")

        mensaje = await ctx.channel.send(embed=embed)
        await database.registrar_ancla_nomina(key_rama, ctx.channel.id, mensaje.id)
        
        await self._actualizar_embed_visual(ctx.guild, key_rama)
        await ctx.respond(f"✅ El Embed fijo para la división `{key_rama.upper()}` ha sido anclado y actualizado.", ephemeral=True)

    @commands.slash_command(name="nominas_gremio", description="[SUPREME] Planta el Embed fijo de la división de Trabajadores Gremiales.")
    async def nominas_gremio(self, ctx: discord.ApplicationContext):
        await self._desplegar_ancla_base(ctx, "gremio")

    @commands.slash_command(name="nominas_guardias", description="[SUPREME] Planta el Embed fijo de la división del Cuerpo de Guardias.")
    async def nominas_guardias(self, ctx: discord.ApplicationContext):
        await self._desplegar_ancla_base(ctx, "guardias")

    @commands.slash_command(name="nominas_world_building", description="[SUPREME] Planta el Embed fijo de la división de World Building.")
    async def nominas_world_building(self, ctx: discord.ApplicationContext):
        await self._desplegar_ancla_base(ctx, "world_building")

    @commands.slash_command(name="nominas_noticias", description="[SUPREME] Planta el Embed fijo de la división de Crónicas y Prensa.")
    async def nominas_noticias(self, ctx: discord.ApplicationContext):
        await self._desplegar_ancla_base(ctx, "noticias")


    # 🛠️ SECCIÓN: AUXILIARES Y SISTEMA INTELIGENTE DE AUTOCOMPLETADO

    def _es_alta_directiva(self, usuario: discord.Member) -> bool:
        """Determina si el usuario es Fundador o Co-Fundador."""
        return any(rol.id in config.ROLES_CREACION_NOMINAS for rol in usuario.roles)

    def _obtener_rama_jefe(self, usuario: discord.Member):
        """Determina a qué división pertenece un Jefe basándose en sus roles."""
        for key, datos in config.CONFIG_RAMAS.items():
            if any(rol.id == datos["jefe_id"] for rol in usuario.roles):
                return key
        return None

    async def _actualizar_embed_visual(self, guild: discord.Guild, key_rama: str):
        """Actualiza el Embed permanente clavado en PERSONAL mostrando Jefes y Lacayos."""
        ancla = await database.obtener_ancla_nomina(key_rama)
        if not ancla: 
            return

        channel_id, message_id = ancla["channel_id"], ancla["message_id"]
        canal = guild.get_channel(channel_id)
        if not canal: 
            return

        try:
            mensaje = await canal.fetch_message(message_id)
        except (discord.NotFound, discord.HTTPException): 
            return

        rama = config.CONFIG_RAMAS[key_rama]
        
        # 1. OPTIMIZACIÓN SENIOR: Extracción directa indexada desde el objeto de Rol de Discord
        rol_jefe = guild.get_role(rama["jefe_id"])
        lista_jefes = rol_jefe.members if rol_jefe else []

        # 2. Consulta de lacayos en el backend (Uso seguro de Row Factory tipo diccionario)
        personal_db = await database.obtener_personal_division(key_rama)

        embed = discord.Embed(title=rama["titulo"], color=rama["color"])
        cuerpo_texto = ""

        # Inyectar Jefes en la cabecera si existen
        if lista_jefes:
            cuerpo_texto += "**👑 JEFATURA DE ÁREA:**\n"
            for jefe in lista_jefes:
                cuerpo_texto += f"• {jefe.mention} — *Líder de División*\n"
            cuerpo_texto += "\n"

        # Inyectar Escalafón Operativo
        cuerpo_texto += "**🛠️ PERSONAL OPERATIVO ASIGNADO:**\n"
        if not personal_db:
            cuerpo_texto += "*No se registran subordinados en los libros de control.*\n"
        else:
            for row in personal_db:
                cuerpo_texto += f"• <@{row['user_id']}> — **{row['rango_interno'].capitalize()}**\n"

        embed.description = cuerpo_texto
        embed.set_footer(text="Registro de Nómina Oficial — Actualizado en vivo")
        await mensaje.edit(embed=embed)

    async def buscar_rangos_autocomplete(self, ctx: discord.AutocompleteContext):
        """Inyecta opciones de rango según la rama determinada para el usuario de forma defensiva."""
        # Si es el Fundador, revisamos de forma segura las opciones de la interacción
        if self._es_alta_directiva(ctx.interaction.user):
            # Pycord expone los valores rellenados de forma directa en ctx.options
            rama_elegida = ctx.options.get("rama")
            
            if rama_elegida and rama_elegida in config.CONFIG_RAMAS:
                return [r.capitalize() for r in config.CONFIG_RAMAS[rama_elegida]["rangos"].keys()]
            return ["Elige primero la rama (Solo Fundadores)"]

        # Si es un jefe normal, auto-detectar su propia sección
        key_rama = self._obtener_rama_jefe(ctx.interaction.user)
        if not key_rama or key_rama not in config.CONFIG_RAMAS: 
            return ["Error: Sin autorización"]
            
        return [r.capitalize() for r in config.CONFIG_RAMAS[key_rama]["rangos"].keys()]


    # 🪓 SECCIÓN: COMANDOS DE CONTROL DE PERSONAL (RECURSOS HUMANOS)

    @commands.slash_command(name="contratar", description="[STAFF] Añade un nuevo lacayo a las filas operativas.")
    async def contratar(
        self, 
        ctx: discord.ApplicationContext, 
        usuario: discord.Option(discord.Member, "Selecciona al miembro a reclutar"),
        rango: discord.Option(str, "Elige el rango correspondiente", autocomplete=buscar_rangos_autocomplete),
        rama: discord.Option(str, "SÓLO FUNDADOR: Elige la sección destino", choices=[
            discord.OptionChoice("🏛️ Trabajadores Gremiales", "gremio"),
            discord.OptionChoice("🛡️ Cuerpo de Guardias", "guardias"),
            discord.OptionChoice("🔮 World Building", "world_building"),
            discord.OptionChoice("📰 Prensa y Noticias", "noticias")
        ], required=False, default=None)
    ):
        es_directiva = self._es_alta_directiva(ctx.user)
        key_rama = rama if es_directiva and rama else self._obtener_rama_jefe(ctx.user)

        if not key_rama:
            await ctx.respond("❌ **Acceso Denegado:** No eres un Jefe de Área ni perteneces a la Alta Directiva Suprema.", ephemeral=True)
            return

        rango_clean = rango.lower()
        rama_data = config.CONFIG_RAMAS[key_rama]

        if rango_clean not in rama_data["rangos"]:
            await ctx.respond("❌ **Error:** Ese rango no pertenece a la división gremial seleccionada.", ephemeral=True)
            return

        # Registro en Base de Datos e Inyección atómica de rol en Discord
        await database.actualizar_miembro_personal(usuario.id, key_rama, rango_clean)
        rol_objetivo = ctx.guild.get_role(rama_data["rangos"][rango_clean])
        if rol_objetivo: 
            await usuario.add_roles(rol_objetivo, reason=f"Contratación firmada por {ctx.user.name}")

        await ctx.respond(f"💼 Registro de contratación completado para {usuario.name} en la rama `{key_rama.upper()}`.", ephemeral=True)
        await self._actualizar_embed_visual(ctx.guild, key_rama)

        canal_logs = ctx.guild.get_channel(CANAL_LOGS_ID)
        if canal_logs:
            embed_log = discord.Embed(
                title="📝 AUDITORÍA: NUEVO CONTRATO",
                description=f"**Sujeto:** {usuario.mention}\n"
                            f"**Rango Otorgado:** {rango.capitalize()}\n"
                            f"**Sección:** {rama_data['titulo']}",
                color=rama_data["color"]
            )
            embed_log.set_footer(text=f"Orden autorizada por: {ctx.user.name}")
            await canal_logs.send(embed=embed_log)

    @commands.slash_command(name="despedir", description="[STAFF] Pone fin al contrato de un lacayo.")
    async def despedir(
        self, 
        ctx: discord.ApplicationContext, 
        usuario: discord.Option(discord.Member, "Selecciona al miembro a expulsar"),
        rama: discord.Option(str, "SÓLO FUNDADOR: Especifica la rama si eres Directiva Suprema", choices=[
            discord.OptionChoice("🏛️ Trabajadores Gremiales", "gremio"),
            discord.OptionChoice("🛡️ Cuerpo de Guardias", "guardias"),
            discord.OptionChoice("🔮 World Building", "world_building"),
            discord.OptionChoice("📰 Prensa y Noticias", "noticias")
        ], required=False, default=None)
    ):
        es_directiva = self._es_alta_directiva(ctx.user)
        key_rama = rama if es_directiva and rama else self._obtener_rama_jefe(ctx.user)

        if not key_rama:
            await ctx.respond("❌ No autorizado.", ephemeral=True)
            return

        personal_actual = await database.obtener_personal_division(key_rama)
        if not any(row["user_id"] == usuario.id for row in personal_actual):
            await ctx.respond("❌ **Error:** Ese usuario no figura en los libros de esa división.", ephemeral=True)
            return

        rama_data = config.CONFIG_RAMAS[key_rama]
        
        # OPTIMIZACIÓN SENIOR (Bolt ⚡): Filtrado O(N) directo sin búsquedas a la caché con get_role()
        rangos_ids = set(rama_data["rangos"].values())
        roles_a_remover = [rol for rol in usuario.roles if rol.id in rangos_ids]
                
        if roles_a_remover:
            await usuario.remove_roles(*roles_a_remover, reason=f"Rescisión de contrato por {ctx.user.name}")

        await database.remover_miembro_personal(usuario.id)
        await ctx.respond(f"🧹 Has despedido a {usuario.name} de la división `{key_rama.upper()}`.", ephemeral=True)
        await self._actualizar_embed_visual(ctx.guild, key_rama)

        canal_logs = ctx.guild.get_channel(CANAL_LOGS_ID)
        if canal_logs:
            embed_log = discord.Embed(
                title="🪓 AUDITORÍA: RESCISIÓN DE CONTRATO",
                description=f"**Sujeto Expulsado:** {usuario.mention}\n"
                            f"**Sección:** {rama_data['titulo']}",
                color=discord.Color.dark_red()
            )
            embed_log.set_footer(text=f"Rescisión ejecutada por: {ctx.user.name}")
            await canal_logs.send(embed=embed_log)

    @commands.slash_command(name="promote", description="[STAFF] Asciende a un trabajador de rango.")
    async def promote(
        self, 
        ctx: discord.ApplicationContext, 
        usuario: discord.Option(discord.Member, "Selecciona al trabajador"),
        nuevo_rango: discord.Option(str, "Elige el nuevo rango", autocomplete=buscar_rangos_autocomplete),
        rama: discord.Option(str, "SÓLO FUNDADOR: Especifica la rama destino", choices=[
            discord.OptionChoice("🏛️ Trabajadores Gremiales", "gremio"),
            discord.OptionChoice("🛡️ Cuerpo de Guardias", "guardias"),
            discord.OptionChoice("🔮 World Building", "world_building"),
            discord.OptionChoice("📰 Prensa y Noticias", "noticias")
        ], required=False, default=None)
    ):
        es_directiva = self._es_alta_directiva(ctx.user)
        key_rama = rama if es_directiva and rama else self._obtener_rama_jefe(ctx.user)

        if not key_rama:
            await ctx.respond("❌ No autorizado.", ephemeral=True)
            return

        rango_clean = nuevo_rango.lower()
        rama_data = config.CONFIG_RAMAS[key_rama]

        if rango_clean not in rama_data["rangos"]:
            await ctx.respond("❌ Rango inválido.", ephemeral=True)
            return

        # OPTIMIZACIÓN SENIOR (Bolt ⚡): Filtrado O(N) masivo y directo
        rangos_ids = set(rama_data["rangos"].values())
        roles_a_remover = [rol for rol in usuario.roles if rol.id in rangos_ids]
        if roles_a_remover:
            await usuario.remove_roles(*roles_a_remover)

        await database.actualizar_miembro_personal(usuario.id, key_rama, rango_clean)
        rol_nuevo = ctx.guild.get_role(rama_data["rangos"][rango_clean])
        if rol_nuevo: 
            await usuario.add_roles(rol_nuevo, reason=f"Ascenso aplicado por {ctx.user.name}")

        await ctx.respond(f"⭐ Ascenso aplicado a {usuario.name}.", ephemeral=True)
        await self._actualizar_embed_visual(ctx.guild, key_rama)

        canal_logs = ctx.guild.get_channel(CANAL_LOGS_ID)
        if canal_logs:
            embed_log = discord.Embed(
                title="⭐ AUDITORÍA: ASCENSO",
                description=f"**Sujeto Promovido:** {usuario.mention}\n"
                            f"**Nuevo Rango:** {nuevo_rango.capitalize()}\n"
                            f"**Sección:** {rama_data['titulo']}",
                color=discord.Color.dark_green()
            )
            embed_log.set_footer(text=f"Promoción firmada por: {ctx.user.name}")
            await canal_logs.send(embed=embed_log)

    @commands.slash_command(name="demote", description="[STAFF] Degrada a un trabajador.")
    async def demote(
        self, 
        ctx: discord.ApplicationContext, 
        usuario: discord.Option(discord.Member, "Selecciona al trabajador"),
        nuevo_rango: discord.Option(str, "Elige el rango inferior", autocomplete=buscar_rangos_autocomplete),
        rama: discord.Option(str, "SÓLO FUNDADOR: Especifica la rama destino", choices=[
            discord.OptionChoice("🏛️ Trabajadores Gremiales", "gremio"),
            discord.OptionChoice("🛡️ Cuerpo de Guardias", "guardias"),
            discord.OptionChoice("🔮 World Building", "world_building"),
            discord.OptionChoice("📰 Prensa y Noticias", "noticias")
        ], required=False, default=None)
    ):
        es_directiva = self._es_alta_directiva(ctx.user)
        key_rama = rama if es_directiva and rama else self._obtener_rama_jefe(ctx.user)

        if not key_rama:
            await ctx.respond("❌ No autorizado.", ephemeral=True)
            return

        rango_clean = nuevo_rango.lower()
        rama_data = config.CONFIG_RAMAS[key_rama]

        if rango_clean not in rama_data["rangos"]:
            await ctx.respond("❌ Rango inválido.", ephemeral=True)
            return

        # OPTIMIZACIÓN SENIOR (Bolt ⚡): Filtrado O(N) masivo y directo
        rangos_ids = set(rama_data["rangos"].values())
        roles_a_remover = [rol for rol in usuario.roles if rol.id in rangos_ids]
        if roles_a_remover:
            await usuario.remove_roles(*roles_a_remover)

        await database.actualizar_miembro_personal(usuario.id, key_rama, rango_clean)
        rol_nuevo = ctx.guild.get_role(rama_data["rangos"][rango_clean])
        if rol_nuevo: 
            await usuario.add_roles(rol_nuevo, reason=f"Reestructuración aplicada por {ctx.user.name}")

        await ctx.respond(f"🔻 Degradación aplicada a {usuario.name}.", ephemeral=True)
        await self._actualizar_embed_visual(ctx.guild, key_rama)

        canal_logs = ctx.guild.get_channel(CANAL_LOGS_ID)
        if canal_logs:
            embed_log = discord.Embed(
                title="🔻 AUDITORÍA: DEGRADACIÓN",
                description=f"**Sujeto Reasignado:** {usuario.mention}\n"
                            f"**Nuevo Rango (Inferior):** {nuevo_rango.capitalize()}\n"
                            f"**Sección:** {rama_data['titulo']}",
                color=discord.Color.orange()
            )
            embed_log.set_footer(text=f"Degradación firmada por: {ctx.user.name}")
            await canal_logs.send(embed=embed_log)

def setup(bot):
    bot.add_cog(PersonalCog(bot))
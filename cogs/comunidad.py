# cogs/comunidad.py

import discord
from discord.ext import commands
import database
import config

class ComunidadCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="perfil", description="Muestra la matrícula y ficha oficial de un Guerrero del Gremio.")
    async def perfil(
        self, 
        ctx: discord.ApplicationContext, 
        aventurero: discord.Option(discord.Member, "Selecciona al Guerrero", default=None)
    ):
        target = aventurero or ctx.user

        # 1. Validar la existencia del rol de Guerrero oficial en el servidor
        rol_aventurero = ctx.guild.get_role(config.ROL_AVENTURERO)
        if not rol_aventurero or rol_aventurero not in target.roles:
            await ctx.respond(f"❌ {target.mention} no posee el rol de Guerrero oficial del Gremio.", ephemeral=True)
            return

        # 2. Consulta al pool persistente de la base de datos
        ficha = await database.obtener_personaje(target.id)
        if not ficha:
            await ctx.respond(f"⚠️ El usuario {target.mention} tiene el rol de Guerrero, pero no se encontró un registro inyectado en la matrícula. Contacta a alguien del Gremio.", ephemeral=True)
            return

        # 3. ADAPTACIÓN SENIOR: Acceso semántico seguro mediante las llaves del diccionario de la base de datos
        # Esto blinda el Cog contra cualquier reestructuración o adición futura de columnas en SQLite
        name = ficha["char_name"]
        race = ficha["char_race"]
        char_class = ficha["char_class"]
        age = ficha["char_age"]
        height = ficha["char_height"]
        link = ficha["sheet_link"]
        nivel = ficha["nivel"]

        # 4. Sanitización estética en caliente para el renderizado del Embed institucional
        embed = discord.Embed(
            title=f"📜 MATRÍCULA OFICIAL: {name.upper()}",
            description=f"Registro inmutable del Guerrero vinculado a la cuenta de {target.mention}.",
            color=discord.Color.dark_gold()
        )
        
        if target.avatar:
            embed.set_thumbnail(url=target.avatar.url)

        # Inyección jerárquica de campos informativos limpia y legible
        embed.add_field(name="⭐ Nivel del Personaje", value=f"**Nivel {nivel}**", inline=False)
        embed.add_field(name="🧬 Raza", value=race.capitalize(), inline=True)
        embed.add_field(name="⚔️ Clase", value=char_class.capitalize(), inline=True)
        embed.add_field(name="⏳ Edad", value=f"{age} años", inline=True)
        embed.add_field(name="📏 Estatura", value=height, inline=True)
        embed.add_field(name="🔗 Hoja de Personaje", value=f"[Enlace a Nivel20]({link})", inline=False)
        
        embed.set_footer(text="Gremio de Guerreros • Datos Protegidos e Inmutables")

        view = None

        # Validación de roles para poder ver el inventario ajeno
        # Fundador, Co-Fundador, Jefe Gremial, Jefe de Guardias
        ROLES_PERMITIDOS_INVENTARIO = [
            1509952429586780332,  # Fundador
            1509954249436696758,  # Co-Fundador
            1509954655470485645,  # Jefe Gremial
            1510094198005694594   # Jefe de Guardias
        ]

        tiene_permiso = ctx.user.id == target.id or any(rol.id in ROLES_PERMITIDOS_INVENTARIO for rol in ctx.user.roles)

        if tiene_permiso:
            view = discord.ui.View()
            boton_inventario = discord.ui.Button(
                label="Abrir Inventario",
                style=discord.ButtonStyle.primary,
                emoji="🎒",
                custom_id=f"inventario_{target.id}" # Asociamos el ID del target al botón para saber de quién es el inventario
            )

            # Callback temporal/interno o global.
            # En este caso, como los botones en Vistas pueden caducar si el bot se reinicia,
            # usaríamos una clase persistente, pero aquí podemos adjuntar la función local para simplificar
            # la interacción efímera (dura mientras la vista no caduque).
            async def btn_callback(interaction: discord.Interaction):
                # Para mayor modularidad, llamamos al comando /inventario directamente
                # pero los slash commands son complejos de invocar así. Renderizamos la vista aquí:
                await interaction.response.defer(ephemeral=True)

                inventario_db = await database.obtener_inventario_usuario(target.id)
                if not inventario_db:
                    await interaction.followup.send(f"🎒 El inventario de **{name}** está vacío.", ephemeral=True)
                    return

                inv_embed = discord.Embed(
                    title=f"🎒 INVENTARIO DE {name.upper()}",
                    description="Objetos adquiridos en el Gremio.",
                    color=discord.Color.blue()
                )

                # Cargar UI Interactiva para usar objetos si el inventario es propio
                inv_view = None
                if interaction.user.id == target.id:
                    inv_view = InventarioInteractivaView(target.id, inventario_db, name)

                await interaction.followup.send(embed=inv_embed, view=inv_view, ephemeral=True)

            boton_inventario.callback = btn_callback
            view.add_item(boton_inventario)

        await ctx.respond(embed=embed, view=view)

    @commands.slash_command(name="inventario", description="Abre tu inventario de objetos adquiridos o el de otro guerrero si eres administrador.")
    async def inventario(self, ctx: discord.ApplicationContext, aventurero: discord.Option(discord.Member, "Revisar el inventario de (Solo Alta Dirección)", default=None)):
        target = aventurero or ctx.user

        # Validar permisos
        ROLES_PERMITIDOS_INVENTARIO = [
            1509952429586780332,  # Fundador
            1509954249436696758,  # Co-Fundador
            1509954655470485645,  # Jefe Gremial
            1510094198005694594   # Jefe de Guardias
        ]

        tiene_permiso = ctx.user.id == target.id or any(rol.id in ROLES_PERMITIDOS_INVENTARIO for rol in ctx.user.roles)
        if not tiene_permiso:
            await ctx.respond("❌ **Acceso Denegado:** No tienes permiso para revisar el inventario de otros guerreros.", ephemeral=True)
            return

        await ctx.response.defer(ephemeral=True)

        ficha = await database.obtener_personaje(target.id)
        nombre = ficha["char_name"] if ficha else target.display_name

        inventario_db = await database.obtener_inventario_usuario(target.id)
        if not inventario_db:
            await ctx.followup.send(f"🎒 El inventario de **{nombre}** está vacío.", ephemeral=True)
            return

        inv_embed = discord.Embed(
            title=f"🎒 INVENTARIO DE {nombre.upper()}",
            description="Objetos adquiridos en las tiendas del Gremio.",
            color=discord.Color.blue()
        )

        for item in inventario_db:
            inv_embed.add_field(name=f"• {item['producto_nombre']}", value=f"Cantidad: **{item['cantidad']}**", inline=False)

        inv_view = None
        if ctx.user.id == target.id:
            inv_view = InventarioInteractivaView(target.id, inventario_db, nombre)

        await ctx.followup.send(embed=inv_embed, view=inv_view, ephemeral=True)


class SelectUsoInventario(discord.ui.Select):
    def __init__(self, target_id: int, inventario_db: list, nombre_pj: str):
        self.target_id = target_id
        self.nombre_pj = nombre_pj

        # Máximo de 25 opciones permitidas por Discord
        options = []
        for item in inventario_db[:25]:
            options.append(discord.SelectOption(
                label=item["producto_nombre"],
                description=f"Cantidad: {item['cantidad']}",
                value=item["producto_nombre"],
                emoji="🎒"
            ))

        super().__init__(placeholder="Selecciona un objeto para usarlo...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        objeto_elegido = self.values[0]

        # Reducir stock o eliminar si llega a 0
        exito = await database.usar_item_inventario(self.target_id, objeto_elegido)

        if exito:
            await interaction.followup.send(f"🧪 **Objeto utilizado:** Has consumido/usado 1x `{objeto_elegido}`.", ephemeral=True)

            # para que los demás jugadores sepan que usó una poción o ración.
            try:
                await interaction.channel.send(f"🎒 El guerrero **{self.nombre_pj}** ha utilizado un objeto: `{objeto_elegido}`.")
            except discord.Forbidden:
                pass # Si el bot no tiene permisos de escritura, no hace nada
        else:
            await interaction.followup.send(f"❌ **Error:** No tienes `{objeto_elegido}` en tu inventario o ocurrió un problema.", ephemeral=True)


class InventarioInteractivaView(discord.ui.View):
    def __init__(self, target_id: int, inventario_db: list, nombre_pj: str):
        super().__init__(timeout=300)
        self.add_item(SelectUsoInventario(target_id, inventario_db, nombre_pj))


def setup(bot):
    bot.add_cog(ComunidadCog(bot))
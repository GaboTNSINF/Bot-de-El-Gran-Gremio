# cogs/tienda.py

import discord
from discord.ext import commands
import json

import database
from config import ROLES_EDICION_MATRICULA

class SelectCategoriaTienda(discord.ui.Select):
    """Menú desplegable para navegar el catálogo dinámico desde la BD."""
    def __init__(self, categorias_disponibles: list):
        options = []
        for cat in categorias_disponibles:
            # Agregamos emojis por defecto dependiendo de la categoría si es conocida
            emoji = "📦"
            if cat.lower() == "armas": emoji = "⚔️"
            elif cat.lower() == "armaduras": emoji = "🛡️"
            elif cat.lower() == "consumibles": emoji = "🧪"

            options.append(discord.SelectOption(label=cat.capitalize(), value=cat, emoji=emoji))

        super().__init__(placeholder="Abre el catálogo gremial...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        # BLINDAJE: Defer instantáneo para que la interacción no caduque.
        await interaction.response.defer(ephemeral=True)

        categoria_elegida = self.values[0]
        catalogo_completo = await database.obtener_catalogo()

        # Filtramos los items de la base de datos por la categoría seleccionada
        items = [item for item in catalogo_completo if item["categoria"].lower() == categoria_elegida.lower()]

        embed = discord.Embed(
            title=f"🏪 CATÁLOGO GREMIAL: {categoria_elegida.upper()}",
            description="Aquí tienes la mercancía disponible en los almacenes.",
            color=discord.Color.gold()
        )

        for item in items:
            embed.add_field(
                name=f"🛒 {item['nombre']} — **{item['precio_str']}**",
                value=f"*{item['descripcion']}*\n(Comprar: `/comprar \"{item['nombre']}\"`)",
                inline=False
            )

        embed.set_footer(text="Anota el nombre exacto del objeto para usar el comando /comprar")
        await interaction.followup.send(embed=embed, ephemeral=True)


class TiendaView(discord.ui.View):
    def __init__(self, categorias: list):
        super().__init__(timeout=300)
        self.add_item(SelectCategoriaTienda(categorias))


class TiendaCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="tienda", description="Abre el catálogo interactivo del Gremio de forma privada.")
    async def tienda(self, ctx: discord.ApplicationContext):
        # de rol donde los demás están escribiendo.
        catalogo = await database.obtener_catalogo()
        if not catalogo:
            await ctx.respond("❌ **La tienda está vacía actualmente.** Los administradores aún no han añadido productos.", ephemeral=True)
            return

        # Extraemos las categorías únicas disponibles en el catálogo
        categorias = list(set(item["categoria"] for item in catalogo))

        embed = discord.Embed(
            title="🏪 BIENVENIDO A LA TIENDA DEL GREMIO",
            description="Selecciona una categoría en el menú inferior para ver nuestros productos.\n\n*Nota: Cuando sepas qué quieres, usa `/comprar <objeto>` para que se te deduzca el oro y se guarde en tu inventario.*",
            color=discord.Color.dark_gold()
        )
        await ctx.respond(embed=embed, view=TiendaView(categorias), ephemeral=True)

    @commands.slash_command(name="comprar", description="Adquiere un objeto de la tienda pagando con tus fondos gremiales.")
    async def comprar(self, ctx: discord.ApplicationContext, objeto: discord.Option(str, "Escribe el nombre del objeto tal cual sale en la /tienda")):
        await ctx.response.defer(ephemeral=True)

        objeto_buscado = objeto.lower().strip()
        catalogo = await database.obtener_catalogo()

        item_encontrado = None
        for item in catalogo:
            if item["nombre"].lower() == objeto_buscado:
                item_encontrado = item
                break

        if not item_encontrado:
            await ctx.followup.send(f"❌ **El objeto `{objeto}` no existe en el catálogo.** Escribe `/tienda` para revisar los nombres exactos.", ephemeral=True)
            return

        costo_cobre = item_encontrado["costo_pc"]

        # Delegate business logic to atomic DB function
        exito = await database.procesar_compra_gremial(ctx.user.id, item_encontrado["nombre"], costo_cobre)

        if not exito:
            await ctx.followup.send(f"❌ **Fondos Insuficientes:** No tienes las `{item_encontrado['precio_str']}` necesarias para comprar el objeto `{item_encontrado['nombre']}`.", ephemeral=True)
            return

        embed_recibo = discord.Embed(
            title="🧾 COMPROBANTE DE COMPRA OFICIAL",
            description=f"Has adquirido suministros en las tiendas del Gremio.",
            color=discord.Color.green()
        )
        embed_recibo.add_field(name="🎒 Objeto Adquirido", value=f"**{item_encontrado['nombre']}**", inline=True)
        embed_recibo.add_field(name="💰 Importe Pagado", value=f"`{item_encontrado['precio_str']}`", inline=True)
        embed_recibo.set_footer(text="El objeto ha sido añadido a tu inventario. ¡Usa /inventario para verlo!")

        await ctx.followup.send(embed=embed_recibo, ephemeral=True)

        from config import CANAL_LOGS_ID
        log_channel = self.bot.get_channel(CANAL_LOGS_ID)
        if log_channel:
            await log_channel.send(f"💸 [TIENDA] {ctx.user.mention} compró `{item_encontrado['nombre']}` por {item_encontrado['precio_str']}.")

    @commands.slash_command(name="agregar_producto", description="[ADMIN] Añade un nuevo producto al catálogo de la tienda.")
    async def agregar_producto(self, ctx: discord.ApplicationContext,
                               nombre: discord.Option(str, "Nombre del producto"),
                               precio_cantidad: discord.Option(int, "Cantidad de la moneda (ej: 15)"),
                               precio_moneda: discord.Option(str, "Tipo de moneda", choices=["Oro (po)", "Plata (pp)", "Cobre (pc)"]),
                               categoria: discord.Option(str, "Categoría", choices=["Armas", "Armaduras", "Consumibles", "Magia", "Otro"]),
                               descripcion: discord.Option(str, "Breve descripción del item")):

        # BLINDAJE: Verificación de permisos
        if not any(role.id in ROLES_EDICION_MATRICULA for role in ctx.user.roles):
            await ctx.respond("❌ **Acceso Denegado:** Solo la Alta Dirección puede modificar el catálogo de la tienda.", ephemeral=True)
            return

        if precio_cantidad <= 0:
            await ctx.respond("❌ **Error:** El precio debe ser mayor a 0.", ephemeral=True)
            return

        await ctx.response.defer(ephemeral=True)

        # Conversión a PC
        costo_pc = precio_cantidad
        precio_str = f"{precio_cantidad} "
        if precio_moneda == "Oro (po)":
            costo_pc *= 100
            precio_str += "po"
        elif precio_moneda == "Plata (pp)":
            costo_pc *= 10
            precio_str += "pp"
        else:
            precio_str += "pc"

        # Revisar si ya existe
        catalogo = await database.obtener_catalogo()
        for item in catalogo:
            if item["nombre"].lower() == nombre.lower():
                await ctx.followup.send(f"❌ **Error:** El producto `{nombre}` ya existe en la tienda.", ephemeral=True)
                return

        # Insertar a la base de datos
        await database.agregar_producto_db(nombre, precio_str, costo_pc, categoria, descripcion)

        await ctx.followup.send(f"✅ **Producto Añadido:** `{nombre}` se agregó a la categoría **{categoria}** por **{precio_str}**.", ephemeral=True)

    @commands.slash_command(name="eliminar_producto", description="[ADMIN] Elimina un producto del catálogo de la tienda.")
    async def eliminar_producto(self, ctx: discord.ApplicationContext, nombre: discord.Option(str, "Nombre exacto del producto a eliminar")):
        # BLINDAJE: Verificación de permisos
        if not any(role.id in ROLES_EDICION_MATRICULA for role in ctx.user.roles):
            await ctx.respond("❌ **Acceso Denegado:** Solo la Alta Dirección puede modificar el catálogo de la tienda.", ephemeral=True)
            return

        await ctx.response.defer(ephemeral=True)

        exito = await database.eliminar_producto_db(nombre)
        if exito:
            await ctx.followup.send(f"✅ **Producto Eliminado:** `{nombre}` ha sido retirado de la tienda.", ephemeral=True)
        else:
            await ctx.followup.send(f"❌ **Error:** No se encontró ningún producto llamado `{nombre}`.", ephemeral=True)

def setup(bot):
    bot.add_cog(TiendaCog(bot))

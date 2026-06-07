# cogs/tienda.py

import discord
from discord.ext import commands
import json

# NOTA EDUCATIVA: En un proyecto grande, los objetos de la tienda cambian constantemente.
# En lugar de hardcodearlos en el código (y tener que reiniciar el bot para añadir una poción),
# es mejor tener un pequeño diccionario que podamos organizar por categorías.
CATALOGO_TIENDA = {
    "armas": [
        {"nombre": "Daga", "precio": "2 po", "costo_pc": 200, "desc": "Daño 1d4 perforante. Sutil y fácil de ocultar."},
        {"nombre": "Espada Corta", "precio": "10 po", "costo_pc": 1000, "desc": "Daño 1d6 cortante. Ligera y versátil."},
        {"nombre": "Espada Larga", "precio": "15 po", "costo_pc": 1500, "desc": "Daño 1d8 cortante (1d10 a dos manos)."},
        {"nombre": "Arco Largo", "precio": "50 po", "costo_pc": 5000, "desc": "Daño 1d8 perforante. Rango 150/600 pies."}
    ],
    "armaduras": [
        {"nombre": "Cuero", "precio": "10 po", "costo_pc": 1000, "desc": "CA 11 + mod. Destreza. Ligera."},
        {"nombre": "Camisa de Mallas", "precio": "50 po", "costo_pc": 5000, "desc": "CA 13 + mod. Destreza (máx 2). Media."},
        {"nombre": "Placas", "precio": "1,500 po", "costo_pc": 150000, "desc": "CA 18. Pesada. Requiere Fuerza 15."}
    ],
    "consumibles": [
        {"nombre": "Poción de Curación", "precio": "50 po", "costo_pc": 5000, "desc": "Restaura 2d4+2 puntos de golpe."},
        {"nombre": "Raciones (1 día)", "precio": "5 pp", "costo_pc": 50, "desc": "Comida básica para sobrevivir."},
        {"nombre": "Antorcha", "precio": "1 pc", "costo_pc": 1, "desc": "Brinda luz brillante por 20 pies."}
    ]
}

class SelectCategoriaTienda(discord.ui.Select):
    """Menú desplegable para navegar el catálogo sin hacer spam en el chat."""
    def __init__(self):
        options = [
            discord.SelectOption(label="Armería (Armas)", description="Espadas, arcos, hachas y más.", emoji="⚔️", value="armas"),
            discord.SelectOption(label="Herrería (Armaduras)", description="Defensa ligera, media y pesada.", emoji="🛡️", value="armaduras"),
            discord.SelectOption(label="Bazar (Consumibles)", description="Pociones, raciones y utilidades.", emoji="🧪", value="consumibles")
        ]
        super().__init__(placeholder="Abre el catálogo gremial...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        # BLINDAJE: Defer instantáneo para que la interacción no caduque.
        await interaction.response.defer()

        categoria_elegida = self.values[0]
        items = CATALOGO_TIENDA[categoria_elegida]

        embed = discord.Embed(
            title=f"🏪 CATÁLOGO GREMIAL: {categoria_elegida.upper()}",
            description="Aquí tienes la mercancía disponible en los almacenes.",
            color=discord.Color.gold()
        )

        for item in items:
            embed.add_field(
                name=f"🛒 {item['nombre']} — **{item['precio']}**",
                value=f"*{item['desc']}*\n(Comprar: `/comprar \"{item['nombre']}\"`)",
                inline=False
            )

        embed.set_footer(text="Anota el nombre exacto del objeto para usar el comando /comprar")
        await interaction.edit_original_response(embed=embed)


class TiendaView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        self.add_item(SelectCategoriaTienda())


class TiendaCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="tienda", description="Abre el catálogo interactivo del Gremio de forma privada.")
    async def tienda(self, ctx: discord.ApplicationContext):
        # NOTA EDUCATIVA: Al usar ephemeral=True, el jugador puede ver el menú sin inundar el canal
        # de rol donde los demás están escribiendo.
        embed = discord.Embed(
            title="🏪 BIENVENIDO A LA TIENDA DEL GREMIO",
            description="Selecciona una categoría en el menú inferior para ver nuestros productos.\n\n*Nota: Cuando sepas qué quieres, usa `/comprar <objeto>` para que se te deduzca el oro.*",
            color=discord.Color.dark_gold()
        )
        await ctx.respond(embed=embed, view=TiendaView(), ephemeral=True)

    @commands.slash_command(name="comprar", description="Adquiere un objeto de la tienda pagando con tus fondos gremiales.")
    async def comprar(self, ctx: discord.ApplicationContext, objeto: discord.Option(str, "Escribe el nombre del objeto tal cual sale en la /tienda")):
        # Buscar el objeto en todas las categorías de forma insensible a mayúsculas
        objeto_buscado = objeto.lower().strip()
        item_encontrado = None

        for categoria in CATALOGO_TIENDA.values():
            for item in categoria:
                if item["nombre"].lower() == objeto_buscado:
                    item_encontrado = item
                    break
            if item_encontrado:
                break

        if not item_encontrado:
            await ctx.respond(f"❌ **El objeto `{objeto}` no existe en el catálogo.** Escribe `/tienda` para revisar los nombres exactos.", ephemeral=True)
            return

        # NOTA EDUCATIVA: Importamos 'database' aquí para evitar dependencias circulares complejas al inicio
        import database

        costo_cobre = item_encontrado["costo_pc"]

        await ctx.response.defer()

        # BLINDAJE DE ECONOMÍA: Usamos transferir_fondos (id 0 = Bóveda Central)
        # Esto deduce el oro atómicamente. Si el jugador no tiene dinero, retorna False.
        exito = await database.transferir_fondos(ctx.user.id, 0, costo_cobre)

        if not exito:
            await ctx.followup.send(f"❌ **Fondos Insuficientes:** No tienes las `{item_encontrado['precio']}` necesarias para comprar el objeto `{item_encontrado['nombre']}`.", ephemeral=True)
            return

        # Si la compra fue exitosa, emitimos un recibo público para la transparencia del Gremio
        embed_recibo = discord.Embed(
            title="🧾 COMPROBANTE DE COMPRA OFICIAL",
            description=f"El aventurero {ctx.user.mention} ha adquirido suministros en las tiendas del Gremio.",
            color=discord.Color.green()
        )
        embed_recibo.add_field(name="🎒 Objeto Adquirido", value=f"**{item_encontrado['nombre']}**", inline=True)
        embed_recibo.add_field(name="💰 Importe Pagado", value=f"`{item_encontrado['precio']}`", inline=True)
        embed_recibo.set_footer(text="Los fondos han sido depositados en la Bóveda Central. ¡No olvides anotar el objeto en tu ficha!")

        await ctx.followup.send(embed=embed_recibo)

def setup(bot):
    bot.add_cog(TiendaCog(bot))

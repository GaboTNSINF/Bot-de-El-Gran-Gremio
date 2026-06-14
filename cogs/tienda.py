# cogs/tienda.py

import discord
from discord.ext import commands

import database
from config import ROLES_EDICION_MATRICULA, CANAL_LOGS_ID

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
        # BLINDAJE DE RED: Defer instantáneo para prevenir la caducidad del token (3000ms TTL).
        await interaction.response.defer(ephemeral=True)

        categoria_elegida = self.values[0]

        # Aislamiento de Red: Extracción microscópica indexada O(log N) directa desde el disco.
        # Erradica la deserialización total en memoria y la lista de comprensión lineal de Python.
        items = await database.obtener_productos_por_categoria(categoria_elegida)

        embed = discord.Embed(
            title=f"🏪 CATÁLOGO GREMIAL: {categoria_elegida.upper()}",
            description="Aquí tienes la mercancía disponible en los almacenes.",
            color=discord.Color.gold()
        )

        LIMITE_MASA_SEGURA = 5800

        # String constante de advertencia post-bucle
        TEXTO_ADVERTENCIA = "\n\n⚠️ **ADVERTENCIA:** *Existen más productos en esta categoría, pero la lista ha sido truncada por límites de información. Contacta a un administrador.*"

        # Reserva Estática Aritmética: Iniciamos la masa pre-calculando el coste de todos los metadatos fijos
        # y reservando por adelantado el costo de la advertencia, garantizando que el bucle deje el espacio exacto.
        texto_footer = "Anota el nombre exacto del objeto para usar el comando /comprar"
        masa_acumulada = len(embed.title) + len(embed.description) + len(TEXTO_ADVERTENCIA) + len(texto_footer)

        campos_procesados = 0
        alerta_disparada = False

        for item in items:
            # Control de Límite de Arrays de la API (Max 25 Fields)
            if campos_procesados >= 25:
                alerta_disparada = True
                break

            nombre_original = item['nombre']
            precio_str = item['precio_str']

            # Restricción Topológica de Pasarela: Límite de Slash Commands de Discord
            # Cortocircuito absoluto si el nombre supera los 100 caracteres.
            if len(nombre_original) > 100:
                alerta_disparada = True
                continue

            # Ensamblaje protegido: 'nombre_original' está matemáticamente garantizado de ser <= 100.
            # Se erradica el bloque if len > 200 (código muerto).
            nombre_campo = f"🛒 {nombre_original} — **{precio_str}**"

            # Validación Predictiva Dinámica para evitar ValueError (> 256) por culpa de 'precio_str'
            if len(nombre_campo) > 256:
                alerta_disparada = True
                continue

            # 2. Validación Predictiva Dinámica y Truncamiento Unitario de 'value' (Max 1024)
            # Libre de sabotaje léxico (sin comillas tipográficas)
            instruccion_compra = f"\n(Comprar: `/comprar {nombre_original}`)"
            descripcion_base = item['descripcion']

            # Cálculo dinámico del espacio remanente, descontando formato
            margen_seguro = 1024 - len(instruccion_compra) - 2

            # Sub-Operatividad
            if margen_seguro < 10:
                alerta_disparada = True
                continue

            if len(descripcion_base) > margen_seguro:
                descripcion_base = descripcion_base[:(margen_seguro - 3)] + "..."

            valor_campo = f"*{descripcion_base}*{instruccion_compra}"

            # 3. Evaluación Predictiva del Payload Global
            costo_proyectado = len(nombre_campo) + len(valor_campo)

            # El límite de masa evalúa contra una masa artificialmente inflada por la Reserva Estática.
            if masa_acumulada + costo_proyectado > LIMITE_MASA_SEGURA:
                alerta_disparada = True
                break

            embed.add_field(name=nombre_campo, value=valor_campo, inline=False)
            masa_acumulada += costo_proyectado
            campos_procesados += 1

        embed.set_footer(text=texto_footer)

        if alerta_disparada:
            # Telemetría local y acoplamiento inofensivo de advertencia pre-costeada
            import logging
            logging.warning(f"[UI RATE LIMIT EVADED] Truncamiento activado en tienda para la categoría '{categoria_elegida}'. Se omitieron registros masivos o malformados.")
            embed.description += TEXTO_ADVERTENCIA

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
        # Diseño UX: Respuesta efímera obligatoria para evitar la contaminación visual del canal de rol activo.
        # Agregación Relacional Nativa: Extracción de huella de memoria optimizada
        categorias = await database.obtener_categorias_unicas()

        if not categorias:
            await ctx.respond("❌ **La tienda está vacía actualmente.** Los administradores aún no han añadido productos.", ephemeral=True)
            return

        embed = discord.Embed(
            title="🏪 BIENVENIDO A LA TIENDA DEL GREMIO",
            description="Selecciona una categoría en el menú inferior para ver nuestros productos.\n\n*Nota: Cuando sepas qué quieres, usa `/comprar <objeto>` para que se te deduzca el oro y se guarde en tu inventario.*",
            color=discord.Color.dark_gold()
        )
        await ctx.respond(embed=embed, view=TiendaView(categorias), ephemeral=True)

    @commands.slash_command(name="comprar", description="Adquiere un objeto de la tienda pagando con tus fondos gremiales.")
    async def comprar(self, ctx: discord.ApplicationContext, objeto: discord.Option(str, "Escribe el nombre del objeto tal cual sale en la /tienda")):
        await ctx.response.defer(ephemeral=True)

        # Delegación O(1) de resolución lógica al motor de persistencia relacional
        item_encontrado = await database.obtener_producto_por_nombre(objeto)

        if not item_encontrado:
            await ctx.followup.send(f"❌ **El objeto `{objeto}` no existe en el catálogo.** Escribe `/tienda` para revisar los nombres exactos.", ephemeral=True)
            return

        costo_cobre = item_encontrado["costo_pc"]

        # Aislamiento de Capa: Delegación a persistencia atómica pura para transferencia unificada de inventario y saldos.
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

        # Resolución Defensiva del Audit Trail (Caché vs. API Rest)
        try:
            log_channel = self.bot.get_channel(CANAL_LOGS_ID)
            if log_channel is None:
                log_channel = await self.bot.fetch_channel(CANAL_LOGS_ID)

            await log_channel.send(f"💸 [TIENDA] {ctx.user.mention} compró `{item_encontrado['nombre']}` por {item_encontrado['precio_str']}.")
        except Exception as e:
            # Fallo crítico de red o permisos: propagamos la alerta internamente.
            import logging
            logging.error(f"Fallo de Auditoría Operacional en Tienda: {e}")

    @commands.slash_command(name="agregar_producto", description="[ADMIN] Añade un nuevo producto al catálogo de la tienda.")
    async def agregar_producto(self, ctx: discord.ApplicationContext,
                               nombre: discord.Option(str, "Nombre del producto"),
                               precio_cantidad: discord.Option(int, "Cantidad de la moneda (ej: 15)"),
                               precio_moneda: discord.Option(str, "Tipo de moneda", choices=["Oro (po)", "Plata (pp)", "Cobre (pc)"]),
                               categoria: discord.Option(str, "Categoría", choices=["Armas", "Armaduras", "Consumibles", "Magia", "Otro"]),
                               descripcion: discord.Option(str, "Breve descripción del item")):

        # BLINDAJE DE JERARQUÍA: Validación estricta contra manipulaciones de matrícula.
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
        # Aislamiento de Red y RAM: Delegación escalar O(log N) para unicidad de nombres.
        # Elimina completamente el escaneo de tabla total y el bucle for sobre la RAM de Python.
        exito = await database.agregar_producto_db(nombre, precio_str, costo_pc, categoria, descripcion)

        if not exito:
            await ctx.followup.send(f"❌ **Error:** El producto `{nombre}` ya existe en la tienda.", ephemeral=True)
            return

        await ctx.followup.send(f"✅ **Producto Añadido:** `{nombre}` se agregó a la categoría **{categoria}** por **{precio_str}**.", ephemeral=True)

    @commands.slash_command(name="eliminar_producto", description="[ADMIN] Elimina un producto del catálogo de la tienda.")
    async def eliminar_producto(self, ctx: discord.ApplicationContext, nombre: discord.Option(str, "Nombre exacto del producto a eliminar")):
        # BLINDAJE DE JERARQUÍA: Validación estricta contra manipulaciones de matrícula.
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

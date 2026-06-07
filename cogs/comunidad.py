# cogs/comunidad.py

import discord
from discord.ext import commands
import database
import config

class ComunidadCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="perfil", description="Muestra la matrícula y ficha oficial de un Aventurero del Gremio.")
    async def perfil(
        self, 
        ctx: discord.ApplicationContext, 
        aventurero: discord.Option(discord.Member, "Selecciona al Aventurero", default=None)
    ):
        target = aventurero or ctx.user

        # 1. Validar la existencia del rol de Aventurero oficial en el servidor
        rol_aventurero = ctx.guild.get_role(config.ROL_AVENTURERO)
        if not rol_aventurero or rol_aventurero not in target.roles:
            await ctx.respond(f"❌ {target.mention} no posee el rol de Aventurero oficial del Gremio.", ephemeral=True)
            return

        # 2. Consulta al pool persistente de la base de datos
        ficha = await database.obtener_personaje(target.id)
        if not ficha:
            await ctx.respond(f"⚠️ El usuario {target.mention} tiene el rol de Aventurero, pero no se encontró un registro inyectado en la matrícula. Contacta a alguien del Gremio.", ephemeral=True)
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
            description=f"Registro inmutable del Aventurero vinculado a la cuenta de {target.mention}.",
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
        
        embed.set_footer(text="Gremio de Aventureros • Datos Protegidos e Inmutables")
        await ctx.respond(embed=embed)

def setup(bot):
    bot.add_cog(ComunidadCog(bot))
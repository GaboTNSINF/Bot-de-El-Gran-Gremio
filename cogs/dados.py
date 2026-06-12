# cogs/dados.py

import discord
from discord.ext import commands
import random
import re

class DadosCog(commands.Cog):
    """Módulo para el lanzamiento de dados de rol (D&D 5e)."""
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="tirar", description="Lanza dados de rol. Ej: 1d20, 2d6+3, 4d8-1")
    async def tirar(self, ctx: discord.ApplicationContext, formula: discord.Option(str, "Fórmula del dado (ej: 1d20, 2d6+3)", required=True)):
        # Buscamos: (cantidad)d(caras)(modificador)
        # Ejemplo: 2d6+3 -> Cantidad=2, Caras=6, Modificador=+3
        patron = r"^(\d+)d(\d+)([+-]\d+)?$"
        match = re.match(patron, formula.lower().strip())

        if not match:
            # Mandamos el error de forma efímera para no ensuciar el chat
            await ctx.respond("❌ **Formato inválido.** Usa el formato clásico de rol: `1d20`, `2d6+3`, `4d8-1`.", ephemeral=True)
            return

        cantidad = int(match.group(1))
        caras = int(match.group(2))
        modificador_str = match.group(3)
        modificador = int(modificador_str) if modificador_str else 0

        # BLINDAJE DE DADOS: Evitar que lancen 1 millón de dados y colapsen el servidor (Límite de 100 dados a la vez)
        if cantidad > 100:
            await ctx.respond("❌ **Límite excedido:** No puedes tirar más de 100 dados a la vez.", ephemeral=True)
            return

        if cantidad <= 0 or caras <= 1:
            await ctx.respond("❌ **Lógica imposible:** Debes tirar al menos 1 dado y debe tener más de 1 cara.", ephemeral=True)
            return

        # Tirar los dados
        resultados = [random.randint(1, caras) for _ in range(cantidad)]
        suma_dados = sum(resultados)
        total_final = suma_dados + modificador

        # Construir el desglose visual (ej: [4, 6] + 3)
        desglose = f"[{', '.join(map(str, resultados))}]"
        if modificador > 0:
            desglose += f" + {modificador}"
        elif modificador < 0:
            desglose += f" - {abs(modificador)}"

        # Determinamos color e íconos para tiradas de d20 (Críticos y Pifias)
        color = discord.Color.blurple()
        nota_critica = ""

        if caras == 20 and cantidad == 1:
            if resultados[0] == 20:
                color = discord.Color.green()
                nota_critica = "🎯 **¡CRÍTICO NATURAL!**"
            elif resultados[0] == 1:
                color = discord.Color.red()
                nota_critica = "💀 **¡PIFIA NATURAL!**"

        embed = discord.Embed(
            title=f"🎲 Tirada de {ctx.user.name}",
            description=f"**Fórmula:** `{formula}`\n**Resultado:** `{total_final}`",
            color=color
        )
        embed.add_field(name="Desglose", value=f"`{desglose}`", inline=False)

        if nota_critica:
            embed.add_field(name="Estado", value=nota_critica, inline=False)

        # TODOS en el canal deben ver el resultado para asegurar que no hay trampas (transparencia).
        await ctx.respond(embed=embed)

def setup(bot):
    bot.add_cog(DadosCog(bot))

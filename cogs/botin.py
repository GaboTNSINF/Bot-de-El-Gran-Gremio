# cogs/botin.py

import discord
from discord.ext import commands
import random

class BotinCog(commands.Cog):
    """Generador de botín aleatorio para facilitar el rol del Dungeon Master."""
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="generar_botin", description="[DM] Genera una tabla de botín aleatoria basada en la dificultad del encuentro.")
    async def generar_botin(
        self,
        ctx: discord.ApplicationContext,
        dificultad: discord.Option(str, "Tier de desafío del encuentro", choices=["Básico (Nivel 1-4)", "Intermedio (Nivel 5-10)", "Avanzado (Nivel 11-16)", "Jefe Épico (Nivel 17+)"])
    ):
        # NOTA EDUCATIVA: Este comando ayuda a los DMs a no tener que inventar el oro en el momento.
        # Las probabilidades están ajustadas para que los jefes den objetos raros y las criaturas básicas solo chatarra.

        monedas_texto = ""
        items_especiales = []
        color_embed = discord.Color.light_gray()

        if dificultad == "Básico (Nivel 1-4)":
            monedas_texto = f"{random.randint(2, 12)} Plata (ppl) y {random.randint(10, 50)} Cobre (pc)"
            color_embed = discord.Color.light_gray()
            # 10% de probabilidad de poción
            if random.randint(1, 100) <= 10:
                items_especiales.append("🧪 Poción de Curación Menor")

        elif dificultad == "Intermedio (Nivel 5-10)":
            monedas_texto = f"{random.randint(10, 40)} Oro (po) y {random.randint(20, 100)} Plata (ppl)"
            color_embed = discord.Color.green()
            if random.randint(1, 100) <= 25:
                items_especiales.append("🧪 Poción de Curación Mayor")
            if random.randint(1, 100) <= 15:
                items_especiales.append("📜 Pergamino de Conjuro (Nivel 2 o 3)")

        elif dificultad == "Avanzado (Nivel 11-16)":
            monedas_texto = f"{random.randint(100, 400)} Oro (po) y {random.randint(10, 50)} Platino (pp)"
            color_embed = discord.Color.blue()
            if random.randint(1, 100) <= 40:
                items_especiales.append("💎 Gema Preciosa (Valor: 500 po)")
            if random.randint(1, 100) <= 20:
                items_especiales.append("🗡️ Arma Mágica Poco Común (+1)")

        else: # Jefe Épico
            monedas_texto = f"{random.randint(1000, 3000)} Oro (po) y {random.randint(100, 500)} Platino (pp)"
            color_embed = discord.Color.gold()
            items_especiales.append("💎 3x Gemas Perfectas (Valor total: 3,000 po)")
            items_especiales.append("🛡️ Objeto Mágico Raro o Muy Raro (A elección del DM)")
            if random.randint(1, 100) <= 50:
                items_especiales.append("👑 Artefacto de Historia (Legendario)")

        embed = discord.Embed(
            title="🎁 BOTÍN DE ENCUENTRO GENERADO",
            description=f"**Dificultad:** `{dificultad}`\nEl bot ha calculado las siguientes recompensas para el grupo:",
            color=color_embed
        )
        embed.add_field(name="💰 Riquezas", value=monedas_texto, inline=False)

        if items_especiales:
            lista_items = "\n".join([f"• {item}" for item in items_especiales])
            embed.add_field(name="✨ Objetos de Interés", value=lista_items, inline=False)
        else:
            embed.add_field(name="✨ Objetos de Interés", value="*Solo chatarra y huesos rotos.*", inline=False)

        embed.set_footer(text="Generador de Loot Gremial para DMs")
        # Mandamos el loot de forma pública para que la mesa entera celebre
        await ctx.respond(embed=embed)

def setup(bot):
    bot.add_cog(BotinCog(bot))

# cogs/taberna.py

import discord
from discord.ext import commands
import random
import asyncio

class TabernaCog(commands.Cog):
    """Módulo de minijuegos y apuestas para gastar el oro del servidor."""
    def __init__(self, bot):
        self.bot = bot

    def _convertir_a_cobre(self, moneda: str, cantidad: int) -> int:
        """Helper para parsear la entrada del jugador a piezas de cobre brutas."""
        escalares = {"cobre": 1, "plata": 10, "oro": 100, "platino": 1000}
        return cantidad * escalares.get(moneda.lower(), 1)

    @commands.slash_command(name="apostar_dados", description="Juega a los dados contra la Casa. Gana el número más alto.")
    async def apostar_dados(
        self,
        ctx: discord.ApplicationContext,
        moneda: discord.Option(str, "Divisa de la apuesta", choices=["Cobre", "Plata", "Oro", "Platino"]),
        cantidad: discord.Option(int, "Cantidad a apostar (Máx 500 po equivalentes)", min_value=1)
    ):
        apuesta_pc = self._convertir_a_cobre(moneda, cantidad)
        # BLINDAJE ECONOMÍA TABERNA: Límite de apuesta para que los jugadores nivel 20 no quiebren la Bóveda de un golpe.
        if apuesta_pc > 50000: # 500 po max
            await ctx.respond("❌ **La Casa rechaza tu apuesta:** El límite máximo por mesa es el equivalente a 500 Oro.", ephemeral=True)
            return

        import database
        await ctx.response.defer()

        # Cobro inicial de la apuesta a la Bóveda Central (Si no hay fondos, la transacción atómica lo frena)
        exito_cobro = await database.transferir_fondos(ctx.user.id, 0, apuesta_pc)
        if not exito_cobro:
            await ctx.followup.send("❌ **No tienes suficientes monedas** para realizar esa apuesta. La guardia te observa con desdén.", ephemeral=True)
            return

        # LA TIRADA (D20 clásico)
        tirada_jugador = random.randint(1, 20)
        tirada_casa = random.randint(1, 20)

        embed = discord.Embed(title="🎲 DADOS DE LA TABERNA 🎲", color=discord.Color.dark_red())
        embed.add_field(name=f"Tirada de {ctx.user.name}", value=f"**{tirada_jugador}**", inline=True)
        embed.add_field(name="Tirada de la Casa", value=f"**{tirada_casa}**", inline=True)

        # LOGICA DE PAGO (House Edge implementado: El empate se lo lleva la casa)
        if tirada_jugador == 20:
            pago = apuesta_pc * 3 # Gana el triple (su apuesta + ganancia doble)
            await database.emitir_fondos_reserva(ctx.user.id, pago)
            embed.color = discord.Color.gold()
            embed.description = f"🎯 **¡CRÍTICO!** El público enloquece. Has ganado el DOBLE de tu apuesta (`{cantidad * 2} {moneda}`)."

        elif tirada_jugador == 1:
            # Pifia: El jugador debe pagar el doble. Se le cobra una vez más la apuesta original.
            exito_penalizacion = await database.transferir_fondos(ctx.user.id, 0, apuesta_pc)
            embed.color = discord.Color.red()
            if exito_penalizacion:
                embed.description = f"💀 **¡PIFIA!** Los dados resbalan de tus manos. Has perdido tu apuesta y la Casa te cobra una multa igual (`-{cantidad} {moneda}` extra)."
            else:
                embed.description = f"💀 **¡PIFIA!** Iban a cobrarte el doble, pero no tienes fondos. Los guardias te arrojan a la calle a patadas."

        elif tirada_jugador > tirada_casa:
            pago = apuesta_pc * 2 # Gana lo normal (recupera su apuesta + 1 de ganancia)
            await database.emitir_fondos_reserva(ctx.user.id, pago)
            embed.color = discord.Color.green()
            embed.description = f"🎉 **¡VICTORIA!** Has superado a la Casa y ganado `{cantidad} {moneda}`."

        else: # tirada_casa >= tirada_jugador (Ventaja de la casa en empate)
            embed.description = f"💸 **DERROTA.** La Casa gana. Pierdes tu apuesta de `{cantidad} {moneda}`."

        await ctx.followup.send(embed=embed)

    @commands.slash_command(name="cubiletes_ilusorios", description="Adivina dónde está la gema. 1 en 3 de ganar.")
    async def cubiletes(
        self,
        ctx: discord.ApplicationContext,
        moneda: discord.Option(str, "Divisa", choices=["Cobre", "Plata", "Oro", "Platino"]),
        cantidad: discord.Option(int, "Cantidad", min_value=1)
    ):
        apuesta_pc = self._convertir_a_cobre(moneda, cantidad)
        if apuesta_pc > 50000:
            await ctx.respond("❌ La apuesta máxima es equivalente a 500 Oro.", ephemeral=True)
            return

        import database
        await ctx.response.defer()

        exito_cobro = await database.transferir_fondos(ctx.user.id, 0, apuesta_pc)
        if not exito_cobro:
            await ctx.followup.send("❌ No tienes fondos para esta apuesta.", ephemeral=True)
            return

        # NOTA EDUCATIVA: Generamos la interfaz de 3 botones de forma dinámica.
        class BotonesCubilete(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=60)
                self.ganador = random.randint(1, 3) # Decidimos antes de que presione

            async def procesar_eleccion(self, interaction: discord.Interaction, eleccion: int):
                # Solo el que apostó puede tocar los botones
                if interaction.user.id != ctx.user.id:
                    await interaction.response.send_message("❌ ¡Eh! No toques las copas de otro jugador.", ephemeral=True)
                    return

                # Inhabilitar botones tras presionar
                for child in self.children:
                    child.disabled = True
                    # Revelar dónde estaba la gema
                    if int(child.custom_id) == self.ganador:
                        child.emoji = "💎"
                        child.style = discord.ButtonStyle.success
                    else:
                        child.emoji = "💨"
                        child.style = discord.ButtonStyle.secondary

                # Re-colorear la elección del jugador si falló
                if eleccion != self.ganador:
                    self.children[eleccion-1].style = discord.ButtonStyle.danger

                await interaction.response.edit_message(view=self)

                if eleccion == self.ganador:
                    # Gana el doble
                    await database.emitir_fondos_reserva(interaction.user.id, apuesta_pc * 2)
                    await interaction.followup.send(f"🎉 **¡ACERTASTE!** Bajo la copa {eleccion} estaba la gema. Has ganado `{cantidad} {moneda}`.", ephemeral=False)
                else:
                    await interaction.followup.send(f"💸 **¡ILUSIÓN!** Elegiste la copa {eleccion}, pero la gema estaba en la {self.ganador}. Has perdido la apuesta.", ephemeral=False)

            @discord.ui.button(label="Copa 1", style=discord.ButtonStyle.primary, custom_id="1")
            async def btn1(self, button: discord.ui.Button, interaction: discord.Interaction):
                await self.procesar_eleccion(interaction, 1)

            @discord.ui.button(label="Copa 2", style=discord.ButtonStyle.primary, custom_id="2")
            async def btn2(self, button: discord.ui.Button, interaction: discord.Interaction):
                await self.procesar_eleccion(interaction, 2)

            @discord.ui.button(label="Copa 3", style=discord.ButtonStyle.primary, custom_id="3")
            async def btn3(self, button: discord.ui.Button, interaction: discord.Interaction):
                await self.procesar_eleccion(interaction, 3)

        embed = discord.Embed(
            title="🪄 LOS CUBILETES ILUSORIOS",
            description=f"El Mago Trilero baraja tres copas velozmente ante {ctx.user.mention}...\nSolo una tiene la gema. Has apostado `{cantidad} {moneda}`.\n\n**¡Elige una copa rápido!**",
            color=discord.Color.purple()
        )
        await ctx.followup.send(embed=embed, view=BotonesCubilete())

def setup(bot):
    bot.add_cog(TabernaCog(bot))

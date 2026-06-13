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


    # 🃏 SECCIÓN: BLACKJACK / VEINTIUNA

    @commands.slash_command(name="blackjack", description="Juega al clásico 21 contra el Croupier del casino.")
    async def blackjack(
        self,
        ctx: discord.ApplicationContext,
        moneda: discord.Option(str, "Divisa de la apuesta", choices=["Cobre", "Plata", "Oro", "Platino"]),
        cantidad: discord.Option(int, "Cantidad a apostar (Máx 500 po equivalentes)", min_value=1)
    ):
        apuesta_pc = self._convertir_a_cobre(moneda, cantidad)
        if apuesta_pc > 50000:
            await ctx.respond("❌ El límite de apuesta para las mesas VIP es de 500 Oro.", ephemeral=True)
            return

        import database
        await ctx.response.defer()

        # Cobro inicial
        exito_cobro = await database.transferir_fondos(ctx.user.id, 0, apuesta_pc)
        if not exito_cobro:
            await ctx.followup.send("❌ Tus bolsillos están vacíos. Retírate de la mesa.", ephemeral=True)
            return

        # Creamos una baraja infinita (con reemplazo) para simplificar la lógica de memoria,
        # asignando valores fijos a las figuras (J, Q, K = 10) y Ases (11 o 1 según convenga).
        cartas = [2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10, 11] * 4

        def pedir_carta():
            return random.choice(cartas)

        def calcular_mano(mano):
            total = sum(mano)
            ases = mano.count(11)
            # El As vale 1 si nos pasamos de 21
            while total > 21 and ases > 0:
                total -= 10
                ases -= 1
            return total

        # Manos iniciales
        mano_jugador = [pedir_carta(), pedir_carta()]
        mano_casa = [pedir_carta(), pedir_carta()]

        class BlackjackView(discord.ui.View):
            def __init__(self, taberna_cog):
                super().__init__(timeout=120)
                self.cog = taberna_cog

            def crear_embed_juego(self, ocultar_casa=True, estado="En curso"):
                total_jugador = calcular_mano(mano_jugador)

                # Visualización de la casa
                if ocultar_casa:
                    texto_casa = f"🎴 [Carta Oculta], {mano_casa[1]}\n**Total Visible:** {mano_casa[1]}"
                else:
                    total_casa = calcular_mano(mano_casa)
                    texto_casa = f"🃏 {mano_casa}\n**Total:** {total_casa}"

                color = discord.Color.blue()
                if "¡Victoria!" in estado or "Blackjack!" in estado: color = discord.Color.green()
                elif "Empate" in estado: color = discord.Color.gold()
                elif "Derrota" in estado or "¡Te pasaste!" in estado: color = discord.Color.red()

                embed = discord.Embed(title="🃏 MESA DE BLACKJACK 🃏", description=estado, color=color)
                embed.add_field(name=f"Mano de {ctx.user.name}", value=f"🃏 {mano_jugador}\n**Total:** {total_jugador}", inline=True)
                embed.add_field(name="Mano de la Casa", value=texto_casa, inline=True)
                embed.set_footer(text=f"Apuesta en juego: {cantidad} {moneda}")
                return embed

            async def finalizar_juego(self, interaction: discord.Interaction, embed, total_jugador, total_casa):
                for child in self.children:
                    child.disabled = True

                # Lógica de Pago
                if total_jugador > 21:
                    pass # Pierde (El dinero ya se dedujo al inicio)
                elif total_casa > 21 or total_jugador > total_casa:
                    # Gana
                    await database.emitir_fondos_reserva(ctx.user.id, apuesta_pc * 2)
                elif total_jugador == total_casa:
                    # Empate (Push) - Recupera su apuesta original sin ganancias
                    await database.emitir_fondos_reserva(ctx.user.id, apuesta_pc)

                await interaction.response.edit_message(embed=embed, view=self)

            @discord.ui.button(label="Pedir (Hit)", style=discord.ButtonStyle.primary, emoji="👇")
            async def pedir(self, button: discord.ui.Button, interaction: discord.Interaction):
                if interaction.user.id != ctx.user.id:
                    return await interaction.response.send_message("❌ Esta no es tu mano.", ephemeral=True)

                mano_jugador.append(pedir_carta())
                total_jugador = calcular_mano(mano_jugador)

                if total_jugador > 21:
                    embed = self.crear_embed_juego(ocultar_casa=False, estado="💀 **¡Te pasaste! Derrota.** La Casa se queda con tu dinero.")
                    await self.finalizar_juego(interaction, embed, total_jugador, calcular_mano(mano_casa))
                else:
                    await interaction.response.edit_message(embed=self.crear_embed_juego())

            @discord.ui.button(label="Plantarse (Stand)", style=discord.ButtonStyle.danger, emoji="✋")
            async def plantarse(self, button: discord.ui.Button, interaction: discord.Interaction):
                if interaction.user.id != ctx.user.id:
                    return await interaction.response.send_message("❌ Esta no es tu mano.", ephemeral=True)

                total_jugador = calcular_mano(mano_jugador)
                total_casa = calcular_mano(mano_casa)

                # La casa está obligada a pedir si tiene 16 o menos
                while total_casa < 17:
                    mano_casa.append(pedir_carta())
                    total_casa = calcular_mano(mano_casa)

                estado = ""
                if total_casa > 21:
                    estado = f"🎉 **¡La Casa se pasó ({total_casa})! ¡Victoria!** Ganas `{cantidad} {moneda}` de beneficio."
                elif total_jugador > total_casa:
                    estado = f"🎉 **¡Victoria!** Superas a la Casa ({total_jugador} vs {total_casa})."
                elif total_jugador < total_casa:
                    estado = f"💸 **Derrota.** La Casa gana ({total_casa} vs {total_jugador})."
                else:
                    estado = "🤝 **Empate (Push).** Recuperas tu apuesta."

                embed = self.crear_embed_juego(ocultar_casa=False, estado=estado)
                await self.finalizar_juego(interaction, embed, total_jugador, total_casa)

        # Validación automática de Blackjack natural al repartir las cartas
        total_inicial_jugador = calcular_mano(mano_jugador)
        total_inicial_casa = calcular_mano(mano_casa)

        view = BlackjackView(self)

        if total_inicial_jugador == 21:
            if total_inicial_casa == 21:
                # Empate de Blackjacks
                embed = view.crear_embed_juego(ocultar_casa=False, estado="🤝 **¡Doble Blackjack! Empate.** Recuperas tu apuesta.")
                await database.emitir_fondos_reserva(ctx.user.id, apuesta_pc)
            else:
                # El jugador sacó 21 a la primera (El Blackjack clásico suele pagar 3 a 2, aquí daremos ganancia doble total para recompensar)
                embed = view.crear_embed_juego(ocultar_casa=False, estado=f"🃏 **¡BLACKJACK NATURAL!** Ganas automáticamente `{cantidad * 2} {moneda}` extra.")
                await database.emitir_fondos_reserva(ctx.user.id, apuesta_pc * 3)

            for child in view.children: child.disabled = True
            await ctx.followup.send(embed=embed, view=view)
            return

        # Si no hubo 21 instantáneo, sigue el juego con la interfaz activa
        await ctx.followup.send(embed=view.crear_embed_juego(), view=view)


def setup(bot):
    bot.add_cog(TabernaCog(bot))

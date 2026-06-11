# cogs/economia.py

import discord
from discord.ext import commands
import config
import database

# ID del canal privado donde el bot enviará los registros de auditoría
CANAL_LOGS_ID = 1513250885730570442

class EconomiaCog(commands.Cog):
    """Módulo maestro encargado de la lógica transaccional y el control bancario del Gremio."""
    def __init__(self, bot):
        self.bot = bot
        # Mapeo estático centralizado para el renderizado unificado de divisas en los Embeds
        self.DIVISAS_METADATA = {
            "platino": {"emoji": "🪙", "sigla": "pp", "nombre": "Platino"},
            "oro":     {"keys": "🥇", "sigla": "po", "nombre": "Oro"},
            "plata":   {"emoji": "🥈", "sigla": "ppl", "nombre": "Plata"},
            "cobre":   {"emoji": "🟫", "sigla": "pc", "nombre": "Cobre"}
        }

    def _convertir_a_cobre(self, moneda: str, cantidad: int) -> int:
        """Helper analítico que normaliza cualquier divisa a piezas de cobre brutas."""
        escalares = {
            "cobre": 1,
            "plata": 10,
            "oro": 100,
            "platino": 1000
        }
        return cantidad * escalares.get(moneda.lower(), 1)

    def _desglosar_cobre(self, total_cobre: int) -> str:
        """Helper matemático que realiza la división modular para formatear los monederos."""
        cobre_restante = total_cobre
        platino = cobre_restante // 1000
        cobre_restante %= 1000
        oro = cobre_restante // 100
        cobre_restante %= 100
        plata = cobre_restante // 10
        cobre = cobre_restante % 10

        return f"🪙 **Platino (pp):** `{platino:,}`\n" \
               f"🥇 **Oro (po):** `{oro}`\n" \
               f"🥈 **Plata (ppl):** `{plata}`\n" \
               f"🟫 **Cobre (pc):** `{cobre}`"

    @commands.slash_command(name="boveda_gremial", description="[HIGH STAFF] Consulta el balance de las arcas centrales.")
    async def boveda_gremial(self, ctx: discord.ApplicationContext):
        if not any(rol.id in [1509952429586780332, 1509954249436696758] for rol in ctx.user.roles):
            await ctx.respond("❌ **Acceso Denegado:** No posees las llaves de la Tesorería.", ephemeral=True)
            return

        await ctx.response.defer(ephemeral=True)
        total_cobre = await database.obtener_balance(0)

        embed = discord.Embed(
            title="🏦 TESORERÍA GREMIAL • ARCHIVO DE BALANCES CENTRALES",
            description="Estado contable auditado de la Bóveda Central propiedad del bot del Gremio.",
            color=discord.Color.dark_blue()
        )
        embed.add_field(name="📊 Balance Bruto Total", value=f"`{total_cobre:,} pc` (Piezas de Cobre)", inline=False)
        embed.add_field(name="💰 Desglose Oficial de Divisas", value=self._desglosar_cobre(total_cobre), inline=False)
        
        await ctx.followup.send(embed=embed, ephemeral=True)

    @commands.slash_command(name="dinero", description="Muestra tu estado de cuenta corriente o el de otro Aventurero.")
    async def dinero(self, ctx: discord.ApplicationContext, aventurero: discord.Option(discord.Member, "Selecciona al Aventurero", default=None)):
        target = aventurero or ctx.user
        if target.bot:
            await ctx.respond("❌ **Error Analítico:** Los bots carecen de estado financiero.", ephemeral=True)
            return

        # UX SENIOR: Si consultas tu propio dinero es efímero (privado), si auditas a otro es público
        es_efimero = True if aventurero is None else False
        await ctx.response.defer(ephemeral=es_efimero)
        
        total_cobre = await database.obtener_balance(target.id)

        embed = discord.Embed(
            title=f"💰 ESTADO DE CUENTA: {target.name.upper()}",
            description=f"Libreta contable oficial vinculada a {target.mention}.",
            color=discord.Color.gold() if total_cobre > 0 else discord.Color.dark_gray()
        )
        if target.avatar: 
            embed.set_thumbnail(url=target.avatar.url)

        embed.add_field(name="💼 Fondos Totales Guardados", value=f"`{total_cobre:,} pc` (Efectivo Neto en Cobre)", inline=False)
        embed.add_field(name="🎒 Contenido del Monedero", value=self._desglosar_cobre(total_cobre), inline=False)
        
        await ctx.followup.send(embed=embed)


    # =========================================================================
    # 👑 COMANDO SUPREMO: EMISIÓN DE FONDOS DESDE LA RESERVA (SUELDOS/SUBSIDIOS)
    # =========================================================================

    @commands.slash_command(name="emitir_nominas", description="[SUPREME] Emite los sueldos de todo el personal gremial registrado en nómina de forma masiva.")
    async def emitir_nominas(self, ctx: discord.ApplicationContext):
        if not any(rol.id in [1509952429586780332, 1509954249436696758] for rol in ctx.user.roles):
            await ctx.respond("❌ **Acceso Denegado:** Solo los Fundadores pueden ejecutar el pago de nóminas masivo.", ephemeral=True)
            return

        # NOTA EDUCATIVA: Retrasamos la respuesta porque esta operación es "pesada"
        # (va a leer toda la base de datos de personal y ejecutar decenas de updates).
        await ctx.response.defer(ephemeral=False)

        # Matriz de Sueldos Semanales (En piezas de cobre brutas para inyección directa)
        # Puedes balancear estos montos a futuro. Ej: 50000 pc = 50 po.
        escala_salarial = {
            "jefe": 60000,
            "supervisor": 50000,
            "oficial": 40000,
            "experto": 30000,
            "trabajador": 20000,
            "aprendiz": 10000,
            "guardia": 20000,
            "recluta": 10000,
            "erudito": 30000,
            "dibujante": 20000,
            "constructor": 20000,
            "cronista": 30000,
            "periodista": 20000,
            "locutor": 20000
        }

        total_empleados_pagados = 0
        total_gasto_pc = 0

        # REFACTOR V5: Optimización Industrial. Evitamos llamar N veces a emitir_fondos_reserva (que abría N transacciones)
        # Pre-calculamos todo en memoria (Python) y luego lo disparamos a SQLite en una sola transacción atómica.
        pagos_pendientes = {} # {user_id_str: cantidad_pc}

        # Recuperar y pagar a todos por cada rama registrada en el bot
        for key_rama, datos_rama in config.CONFIG_RAMAS.items():
            # 1. PAGO A LA JEFATURA (Extraído del Rol de Discord, no de la BD)
            rol_jefe = ctx.guild.get_role(datos_rama["jefe_id"])
            if rol_jefe:
                for jefe in rol_jefe.members:
                    sueldo_jefe = escala_salarial["jefe"]
                    pagos_pendientes[str(jefe.id)] = pagos_pendientes.get(str(jefe.id), 0) + sueldo_jefe
                    total_empleados_pagados += 1
                    total_gasto_pc += sueldo_jefe

            # 2. PAGO AL ESCALAFÓN OPERATIVO (Extraído de la BD mediante /contratar)
            personal_rama = await database.obtener_personal_division(key_rama)
            if personal_rama:
                for empleado in personal_rama:
                    u_id = int(empleado["user_id"])
                    rango = empleado["rango_interno"].lower()
                    sueldo_asignado = escala_salarial.get(rango, 10000)

                    pagos_pendientes[u_id] = pagos_pendientes.get(u_id, 0) + sueldo_asignado
                    total_empleados_pagados += 1
                    total_gasto_pc += sueldo_asignado

        if total_empleados_pagados == 0:
            await ctx.followup.send("📝 **Nómina vacía:** No hay personal registrado en los libros del Gremio para cobrar sueldo.")
            return

        # Ejecución Industrial en Base de Datos (1 sola transacción para N usuarios)
        try:
            async with database.db_lock:
                await database._connection.execute("BEGIN")
                # 1. Comprobar liquidez de la Bóveda Central (0)
                async with database._connection.execute("SELECT balance_pc FROM economia_billetera WHERE user_id = 0") as cursor:
                    boveda = await cursor.fetchone()
                    if not boveda or boveda["balance_pc"] < total_gasto_pc:
                        await database._connection.rollback()
                        await ctx.followup.send(f"⚠️ **ALERTA DE BANCARROTA:** La Bóveda (ID 0) no tiene liquidez ({boveda['balance_pc'] if boveda else 0} pc) para cubrir la nómina de {total_gasto_pc} pc. Abortado.")
                        return

                # 2. Restar el bloque masivo a la bóveda
                await database._connection.execute(
                    "UPDATE economia_billetera SET balance_pc = balance_pc - ? WHERE user_id = 0",
                    (total_gasto_pc,)
                )

                # 3. Iterar inserciones seguras (Transacción Bifurcada Retrocompatible V6)
                for u_id, monto in pagos_pendientes.items():
                    await database._connection.execute("INSERT OR IGNORE INTO personajes_estados (user_id) VALUES (?)", (u_id,))
                    await database._connection.execute("INSERT OR IGNORE INTO economia_billetera (user_id, balance_pc) VALUES (?, 0)", (u_id,))
                    await database._connection.execute(
                        "UPDATE economia_billetera SET balance_pc = balance_pc + ? WHERE user_id = ?",
                        (monto, u_id)
                    )
                await database._connection.commit()
        except Exception as e:
            async with database.db_lock:
                await database._connection.rollback()
            await ctx.followup.send(f"❌ **Error Crítico de Dispersión:** {e}. Se ha ejecutado un Rollback manual.")
            return

        # Reporte final

        embed = discord.Embed(
            title="🏦 INFORME DE TESORERÍA: NÓMINAS EMITIDAS",
            description=f"El Fundador {ctx.user.mention} ha ordenado la dispersión de fondos para todo el personal operativo.",
            color=discord.Color.green()
        )
        embed.add_field(name="👥 Personal Remunerado", value=f"`{total_empleados_pagados}` trabajadores", inline=True)
        embed.add_field(name="💸 Gasto Total Gremial", value=f"`{total_gasto_pc:,} pc` deducidos de la Bóveda", inline=True)
        embed.set_footer(text="Los sueldos ya han sido depositados en las cuentas corrientes de los jugadores.")

        await ctx.followup.send(embed=embed)

    @commands.slash_command(name="banco_emitir", description="[SUPREME] Inyecta fondos a un usuario desde la Bóveda Central.")
    async def banco_emitir(
        self,
        ctx: discord.ApplicationContext,
        usuario: discord.Option(discord.Member, "Aventurero receptor de los fondos"),
        moneda: discord.Option(str, "Tipo de divisa a otorgar", choices=[
            discord.OptionChoice("🪙 Platino (pp)", "platino"),
            discord.OptionChoice("🥇 Oro (po)", "oro"),
            discord.OptionChoice("🥈 Plata (ppl)", "plata"),
            discord.OptionChoice("🟫 Cobre (pc)", "cobre")
        ]),
        cantidad: discord.Option(int, "Cantidad de monedas a emitir", min_value=1)
    ):
        if not any(rol.id in [1509952429586780332, 1509954249436696758] for rol in ctx.user.roles):
            await ctx.respond("❌ **Acceso Denegado:** Requiere credenciales de la Alta Directiva Suprema.", ephemeral=True)
            return

        # BLINDAJE DE ECONOMÍA: Filtro de seguridad que valida que la cantidad ingresada sea positiva,
        # esto previene que un admin por error ingrese un negativo e intercepte fondos del usuario.
        if cantidad <= 0:
            await ctx.respond("❌ **Error Transaccional:** La cantidad a emitir debe ser estrictamente mayor a cero.", ephemeral=True)
            return

        # NOTA EDUCATIVA: Retrasamos el envío de respuesta de Discord (defer) para evitar
        # que el comando diga "La aplicación no respondió" si la base de datos se demora.
        await ctx.response.defer(ephemeral=True)
        cobre_bruto = self._convertir_a_cobre(moneda, cantidad)

        # Transacción atómica blindada (Alternativa B en Base de Datos)
        exito = await database.emitir_fondos_reserva(usuario.id, cobre_bruto)

        if not exito:
            await ctx.followup.send("❌ **Bancarrota Técnica:** La Bóveda Central del Gremio no dispone de fondos suficientes para cubrir esta emisión.", ephemeral=True)
            return

        await ctx.followup.send(f"✅ Has emitido exitosamente `{cantidad} {moneda}` desde las arcas del Gremio hacia la cuenta de {usuario.name}.", ephemeral=True)

        # Envío silencioso al canal de Auditoría
        canal_logs = ctx.guild.get_channel(CANAL_LOGS_ID)
        if canal_logs:
            embed_log = discord.Embed(
                title="📜 AUDITORÍA: EMISIÓN DE FONDOS",
                description=f"**Ejecutivo:** {ctx.user.mention}\n"
                            f"**Receptor:** {usuario.mention}\n"
                            f"**Monto Emitido:** `{cantidad} {moneda.upper()}`\n"
                            f"**Concepto:** Financiamiento Oficial / Asignación Directa.",
                color=discord.Color.blue()
            )
            embed_log.set_footer(text="Registro Interno de la Tesorería Central")
            try:
                await canal_logs.send(embed=embed_log)
            except discord.HTTPException as e:
                print(f"⚠️ No se pudo enviar el log de emisión al canal de auditoría debido a un error de API: {e}")


    # =========================================================================
    # 🛡️ COMANDOS DE INCAUTACIÓN Y WIPE ECONÓMICO (BETA)
    # =========================================================================

    @commands.slash_command(name="banco_embargar", description="[SUPREME] Incauta todo el dinero de un usuario y lo devuelve a la Bóveda Central.")
    async def banco_embargar(self, ctx: discord.ApplicationContext, usuario: discord.Option(discord.Member, "Usuario a embargar")):
        if not any(rol.id in [1509952429586780332, 1509954249436696758] for rol in ctx.user.roles):
            await ctx.respond("❌ **Acceso Denegado.**", ephemeral=True)
            return

        await ctx.response.defer(ephemeral=True)
        recuperado_pc = await database.embargar_fondos(usuario.id)

        if recuperado_pc == 0:
            await ctx.followup.send(f"⚠️ El usuario {usuario.name} ya tiene sus bolsillos vacíos.", ephemeral=True)
            return

        await ctx.followup.send(f"⚖️ Se han incautado `{recuperado_pc:,} pc` de {usuario.name}. Los fondos retornaron a la Bóveda.", ephemeral=True)

        canal_logs = ctx.guild.get_channel(CANAL_LOGS_ID)
        if canal_logs:
            embed_log = discord.Embed(
                title="⚖️ AUDITORÍA: EMBARGO FISCAL",
                description=f"**Sujeto:** {usuario.mention}\n"
                            f"**Monto Incautado:** `{recuperado_pc:,} pc`\n"
                            f"**Ejecutor:** {ctx.user.mention}",
                color=discord.Color.dark_red()
            )
            embed_log.set_footer(text="Fondos inyectados de regreso a la Bóveda Central.")
            await canal_logs.send(embed=embed_log)

    @commands.slash_command(name="banco_wipe_beta", description="[SUPREME] Vacía las cuentas de TODO EL SERVIDOR y retorna los fondos a la Bóveda.")
    async def banco_wipe_beta(self, ctx: discord.ApplicationContext):
        if not any(rol.id in [1509952429586780332, 1509954249436696758] for rol in ctx.user.roles):
            await ctx.respond("❌ **Acceso Denegado.** Comando altamente destructivo.", ephemeral=True)
            return

        await ctx.response.defer(ephemeral=False)
        recuperado_total = await database.embargo_masivo()

        embed = discord.Embed(
            title="⚠️ RESETEO ECONÓMICO GLOBAL (WIPE)",
            description="Por decreto de los Fundadores, se ha ejecutado un embargo global sobre todos los habitantes del reino.\n"
                        "Las cuentas han vuelto a 0 y el oro circulante ha retornado a la Tesorería.",
            color=discord.Color.red()
        )
        embed.add_field(name="💰 Oro Total Recuperado", value=f"`{recuperado_total:,} pc`")
        embed.set_footer(text=f"Orden Ejecutada por: {ctx.user.name}")

        await ctx.followup.send(embed=embed)

        canal_logs = ctx.guild.get_channel(CANAL_LOGS_ID)
        if canal_logs:
            await canal_logs.send(embed=embed)


    # =========================================================================
    # ⚔ COMANDO COMERCIAL P2P / TIENDA: INTERCAMBIO LIBRE DE FONDOS
    # =========================================================================

    @commands.slash_command(name="pagar", description="Transfiere monedas de tu propio monedero hacia otro Aventurero o la Tienda.")
    async def pagar(
        self,
        ctx: discord.ApplicationContext,
        usuario: discord.Option(discord.Member, "Selecciona al Aventurero o al Bot del Gremio"),
        moneda: discord.Option(str, "Tipo de divisa a transferir", choices=[
            discord.OptionChoice("🪙 Platino (pp)", "platino"),
            discord.OptionChoice("🥇 Oro (po)", "oro"),
            discord.OptionChoice("🥈 Plata (ppl)", "plata"),
            discord.OptionChoice("🟫 Cobre (pc)", "cobre")
        ]),
        cantidad: discord.Option(int, "Cantidad de monedas a enviar", min_value=1)
    ):
        # BLINDAJE P2P: Validar que los usuarios no puedan enviar monedas en negativo.
        if cantidad <= 0:
            await ctx.respond("❌ **Error Transaccional:** El monto debe ser superior a cero.", ephemeral=True)
            return

        if usuario.id == ctx.user.id:
            await ctx.respond("❌ **Error Transaccional:** No puedes transferir fondos hacia tu propia cuenta corriente.", ephemeral=True)
            return

        if usuario.bot and usuario.id != self.bot.user.id:
            await ctx.respond("❌ **Error Operativo:** Las entidades automatizadas externas no aceptan transacciones comerciales.", ephemeral=True)
            return

        await ctx.response.defer(ephemeral=True)
        cobre_bruto = self._convertir_a_cobre(moneda, cantidad)
        receptor_id = 0 if usuario.id == self.bot.user.id else usuario.id

        # Transferencia P2P atómica libre de condiciones de carrera
        # NOTA EDUCATIVA: Atómico significa que toda la operación en base de datos pasa como un bloque sólido:
        # o el dinero se mueve completo o falla y no pasa nada. Esto impide que se reste dinero pero no se sume,
        # o que un jugador duplique monedas spameando el comando simultáneamente con bots externos.
        exito = await database.transferir_fondos(ctx.user.id, receptor_id, cobre_bruto)

        if not exito:
            await ctx.followup.send(f"❌ **Fondos Insuficientes:** No posees la liquidez necesaria en tu monedero para cubrir esta transferencia de `{cantidad} {moneda}`.", ephemeral=True)
            return

        if receptor_id == 0:
            await ctx.followup.send(f"💸 Has pagado `{cantidad} {moneda}` al Gremio (Fondos depositados en la Bóveda Central).", ephemeral=True)
        else:
            await ctx.followup.send(f"💸 Has transferido `{cantidad} {moneda}` a la cuenta de {usuario.name}.", ephemeral=True)

        # Envío silencioso al canal de Auditoría
        canal_logs = ctx.guild.get_channel(CANAL_LOGS_ID)
        if canal_logs:
            nombre_receptor = "🏛️ BÓVEDA CENTRAL" if receptor_id == 0 else usuario.mention
            embed_log = discord.Embed(
                title="📜 AUDITORÍA: TRANSFERENCIA (P2P)",
                description=f"**Emisor:** {ctx.user.mention}\n"
                            f"**Receptor:** {nombre_receptor}\n"
                            f"**Monto Transferido:** `{cantidad} {moneda.upper()}`",
                color=discord.Color.light_grey() if receptor_id != 0 else discord.Color.gold()
            )
            embed_log.set_footer(text="Auditoría Automática de la Red Bancaria")
            try:
                await canal_logs.send(embed=embed_log)
            except discord.HTTPException as e:
                print(f"⚠️ Falló el log de transferencia P2P en el canal de auditoría debido a restricciones de Discord: {e}")

def setup(bot):
    bot.add_cog(EconomiaCog(bot))
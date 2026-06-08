# cogs/seguridad.py

import discord
from discord.ext import commands
import config
import asyncio

# ID del canal prohibido (La fosa de la guillotina)
CANAL_PROHIBIDO_ID = 1510083208656589032

class SeguridadCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # FILTRO ULTRA-RÁPIDO: Si el mensaje no pertenece al canal prohibido o es de un bot, abortar al instante
        if message.channel.id != CANAL_PROHIBIDO_ID or message.author.bot:
            return

        usuario = message.author
        guild = message.guild
        if not guild:
            return

        # 1. PURGA INMEDIATA DE LA EVIDENCIA (Independiente del rango)
        try:
            await message.delete()
        except (discord.Forbidden, discord.NotFound):
            pass

        # 2. INTENTO DE GUILLOTINA TOTAL (PROTOCOLO ANTI-HACKEO)
        razon_destierro = "ACTIVACIÓN DE TRAMPA RÚNICA: Cuenta comprometida o intrusa en canal prohibido."
        
        try:
            # El bot lanza el kick a matar. Si la cuenta es del Staff o Co-Fundadores inferiores al bot, caerán.
            await guild.kick(usuario, reason=razon_destierro)
            print(f"🪓 [DESTIERRO] {usuario.name} ({usuario.id}) ha sido expulsado fulminantemente por seguridad del ecosistema.")
            
        except discord.Forbidden:
            # 3. PROTOCOLO DE CONTENCIÓN ANTE FALLO DE JERARQUÍA (Dueño o Rango Superior)
            # Si la API impide el kick (porque eres tú o un rol superior intocable), aplicamos tierra quemada localmente
            print(f"⚠️ [CONTENCIÓN CRÍTICA] No se pudo expulsar a {usuario.name} por restricciones de la API de Discord. Iniciando remoción de accesos.")
            
            # Intentamos quitarle todos los roles posibles para quitarle los permisos de Administrador/Staff en caliente
            roles_a_remover = [rol for rol in usuario.roles if rol < guild.me.top_role and rol != guild.default_role]
            
            try:
                if roles_a_remover:
                    await usuario.remove_roles(*roles_a_remover, reason="CONTENCIÓN: Cuenta de alto rango comprometida en canal prohibido.")
                    print(f"🛡️ [CONTENCIÓN] Se han revocado {len(roles_a_remover)} roles administrativos a {usuario.name} para proteger el servidor.")
            except discord.HTTPException as e:
                print(f"❌ No se pudieron remover los roles de contención: {e}")

        except Exception as e:
            print(f"⚠️ Anomalía imprevista en el motor de la guillotina: {e}")

    @discord.slash_command(name="purga", description="Elimina historial de mensajes (Solo Fundador/Co-Fundador).")
    @discord.guild_only()
    async def purga(self, ctx: discord.ApplicationContext, cantidad: discord.Option(int, "Cantidad de mensajes a borrar (Dejar vacío para purga total)", required=False, default=None)): # type: ignore
        """
        Comando exclusivo para Alta Administración (Fundadores)
        Permite purgar un canal completo o una cantidad específica de mensajes.
        Discord restringe la purga masiva a mensajes con un máximo de 14 días de antigüedad.
        Para evitar 'Rate Limits' y congelamiento, aplicamos estricto filtro de fechas (after).
        """
        # --- VALIDACIÓN DE JERARQUÍA (Solo Fundador y Co-Fundador) ---
        # Aseguramos que la lista pertenezca estrictamente a esos dos roles verificados en config.py
        roles_autorizados = [
            1509952429586780332,  # ID Rol Fundador
            1509954249436696758   # ID Rol Co-Fundador
        ]

        # Validación segura en caso de que algún error pase el filtro de guild_only
        if not hasattr(ctx.author, 'roles'):
            await ctx.respond("❌ Este comando solo puede ser usado dentro del servidor.", ephemeral=True)
            return

        autorizado = any(rol.id in roles_autorizados for rol in ctx.author.roles)
        if not autorizado:
            await ctx.respond("❌ No tienes la autoridad requerida (Fundador/Co-Fundador) para invocar este comando.", ephemeral=True)
            return

        # --- AVISO INICIAL (EFÍMERO) ---
        await ctx.respond("🧹 Iniciando protocolo de purga en este canal... Por favor, espera.", ephemeral=True)

        try:
            import datetime
            # Calculamos la fecha de corte exacta: 14 días hacia atrás desde el momento actual en UTC
            # BLINDAJE: Evita que Discord empiece a borrar mensajes 1x1 causando un Rate Limit masivo.
            corte_14_dias = discord.utils.utcnow() - datetime.timedelta(days=14)

            # --- EJECUCIÓN DE PURGA ---
            limit = cantidad if cantidad is not None else 10000

            # purge() con bulk=True (por defecto) y límite de fecha after.
            deleted = await ctx.channel.purge(limit=limit, after=corte_14_dias, bulk=True)

            # --- INFORME FINAL (EFÍMERO) ---
            if len(deleted) > 0:
                await ctx.interaction.edit_original_response(content=f"✅ Protocolo completado. Se han purgado `{len(deleted)}` mensajes.\n*(Nota: Mensajes anteriores a 14 días han sido ignorados por seguridad).*")
            else:
                await ctx.interaction.edit_original_response(content="⚠️ No se borraron mensajes. El canal está vacío o todos los mensajes son más antiguos de 14 días.")

        except discord.Forbidden:
            await ctx.interaction.edit_original_response(content="❌ Error: El bot no tiene permisos suficientes para borrar mensajes en este canal.")
        except discord.HTTPException as e:
            await ctx.interaction.edit_original_response(content=f"❌ Error de la API de Discord al intentar purgar: {e}")


def setup(bot):
    bot.add_cog(SeguridadCog(bot))
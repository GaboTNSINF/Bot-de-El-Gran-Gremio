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

def setup(bot):
    bot.add_cog(SeguridadCog(bot))
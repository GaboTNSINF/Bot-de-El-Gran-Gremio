# cogs/voz.py

import discord
from discord.ext import commands
import config

class VozDinamicaCog(commands.Cog):
    """Módulo asíncrono que intercepta estados de voz para generar salas on-demand con permisos de propietario."""
    def __init__(self, bot):
        self.bot = bot
        # Estructura en memoria RAM para rastrear las IDs de canales creados y sus respectivos dueños
        self.canales_temporales = {} 

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        guild = member.guild
        if not guild:
            return

        # FILTRO DE TRANSICIÓN: Si el canal de origen es idéntico al de destino, ignorar por completo
        # Esto mitiga la sobrecarga en la CPU ante mutings, deafens o transmisiones de streaming dentro del mismo canal
        if before.channel == after.channel:
            return

        # --- FASE 1: DETECCIÓN DE INGRESO AL CANAL HUB (CREACIÓN DE SALA) ---
        if after.channel and after.channel.id == config.CANAL_HUB_VOZ:
            categoria_destino = guild.get_channel(config.CATEGORIA_VOZ_TEMPORAL)
            if not categoria_destino:
                print("⚠️ Error en Módulo Voz: No se encontró la categoría configurada en config.py")
                return

            # Definir la matriz de permisos otorgando control total y exclusivo al creador
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=True, connect=True),
                member: discord.PermissionOverwrite(
                    view_channel=True,
                    connect=True,
                    speak=True,
                    manage_channels=True,    # Capacidad de alterar nombre y límite de slots
                    mute_members=True,       # Capacidad de silenciar infractores en su sala
                    deafen_members=True,     # Capacidad de ensordecer usuarios en su sala
                    move_members=True        # Capacidad de expulsar miembros de su sala
                )
            }

            # BLINDAJE VOZ: Los Viajeros (no registrados) no pueden ver ni entrar a las mesas de juego.
            # En Discord, cuando envías `overwrites` manuales al crear un canal, la herencia de la Categoría se rompe.
            # Por tanto, debemos inyectar la prohibición manualmente aquí.
            rol_viajero = guild.get_role(config.ROL_VIAJERO)
            if rol_viajero:
                overwrites[rol_viajero] = discord.PermissionOverwrite(view_channel=False, connect=False)

            # Crear físicamente el canal de voz temporal en la API de Discord
            nombre_sala = f"🔊 Mesa de {member.name}"
            
            try:
                nuevo_canal = await guild.create_voice_channel(
                    name=nombre_sala,
                    category=categoria_destino,
                    overwrites=overwrites,
                    reason=f"Canal de voz temporal instanciado por {member.name}"
                )
                
                # Registrar de forma atómica la ID del canal en nuestro diccionario de control
                self.canales_temporales[nuevo_canal.id] = member.id
                
                # Transferencia forzosa del Aventurero hacia su propia sala privada instanciada
                await member.move_to(nuevo_canal)
                print(f"🔊 Sala Dinámica '{nombre_sala}' inicializada exitosamente.")
                
            except discord.Forbidden:
                print("❌ Error de Permisos: El bot carece del rango 'Gestionar Canales' o 'Mover Miembros' para instanciar salas.")
            except discord.HTTPException as e:
                print(f"⚠️ Error de red al intentar inicializar sala dinámica: {e}")

        # --- FASE 2: DETECCIÓN DE SALIDA (RECOLECCIÓN DE BASURA MULTI-HILO) ---
        if before.channel and before.channel.id in self.canales_temporales:
            canal_evaluado = before.channel
            
            # Condición de vaciado estricto: Si no queda absolutamente nadie dentro del canal temporal
            if len(canal_evaluado.members) == 0:
                try:
                    # Se ejecuta la eliminación física en la API de Discord primero
                    await canal_evaluado.delete(reason="Remoción automática: Canal temporal remanente con 0 miembros.")
                    
                    # Limpiar la memoria del diccionario ÚNICAMENTE si el borrado fue confirmado con éxito por Discord
                    if canal_evaluado.id in self.canales_temporales:
                        del self.canales_temporales[canal_evaluado.id]
                        
                    print(f"🧹 Basurero de Voz: Canal temporal {canal_evaluado.id} destruido en conformidad.")
                    
                except discord.NotFound:
                    # Mitigar excepciones si el canal fue eliminado concurrentemente a mano por un Administrador
                    if canal_evaluado.id in self.canales_temporales:
                        del self.canales_temporales[canal_evaluado.id]
                        
                except discord.Forbidden:
                    print("❌ Error de Permisos: El bot carece del rango necesario para destruir canales de voz temporales.")
                except discord.HTTPException as e:
                    print(f"⚠️ Alerta de Red: Falló la recolección de basura del canal {canal_evaluado.id} debido a latencia: {e}")

def setup(bot):
    bot.add_cog(VozDinamicaCog(bot))
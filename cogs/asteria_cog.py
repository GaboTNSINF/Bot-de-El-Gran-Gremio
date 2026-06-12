import discord
from discord.ext import commands
import database # Ficticio import para mostrar la intencion

class AsteriaCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    asteria = discord.SlashCommandGroup("asteria", "Comandos del ecosistema Asteria")

    # Módulo A: Reportar Sesión
    @asteria.command(name="reportar_sesion", description="[DM] Reporta una sesión con recompensas.")
    async def reportar_sesion(self, ctx: discord.ApplicationContext):
        # Posteriormente desplegaremos la vista multi-paso (UserSelect).
        await ctx.respond("Inicializando reporte de sesión...", ephemeral=True)
        pass

    # Módulo B: Filtro de Admisión
    @asteria.command(name="unirse_mesa", description="Solicita unirse a la mesa de un DM.")
    async def unirse_mesa(self, ctx: discord.ApplicationContext, dm: discord.Option(discord.Member, "El DM de la mesa")):
        await ctx.respond("Evaluando estado de viaje y extenuación...", ephemeral=True)
        pass

    # Módulo C: Forja y Crafteo
    @asteria.command(name="intentar_forja", description="Intenta forjar un objeto usando una receta.")
    async def intentar_forja(self, ctx: discord.ApplicationContext, receta: str, cincel_id: int):
        # y DELETE WHERE cantidad <= 0 (previamente arreglado el CHECK >= 0).
        await ctx.respond("Intentando forjar...", ephemeral=True)
        pass

    # Módulo D: Auditoría Administrativa
    @asteria.command(name="admin_limpiar_estado", description="[Admin] Limpia estados de viaje o extenuación.")
    async def admin_limpiar_estado(
        self,
        ctx: discord.ApplicationContext,
        usuario: discord.Member,
        motivo: str,
        evidencia: str,
        tipo_limpieza: discord.Option(str, choices=["SOLO_VIAJE", "SOLO_EXTENUACION", "AMBOS"])
    ):
        await ctx.respond("Iniciando auditoría asíncrona...", ephemeral=True)
        pass

    # Nuevo: Consumo de curación local
    @asteria.command(name="consumir_item", description="Consume un objeto de tu inventario.")
    async def consumir_item(self, ctx: discord.ApplicationContext, item: str):
        await ctx.respond("Consumiendo objeto...", ephemeral=True)
        pass

def setup(bot):
    bot.add_cog(AsteriaCog(bot))

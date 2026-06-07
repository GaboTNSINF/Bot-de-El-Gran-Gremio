# cogs/buzon.py

import discord
from discord.ext import commands
import config
import random

class FormularioContenidoBuzon(discord.ui.Modal):
    """Formulario interactivo final que recolecta el contenido del feedback institucional."""
    def __init__(self, es_anonimo: bool):
        # Almacenamos el estado tipado del anonimato de forma interna
        self.es_anonimo = es_anonimo
        super().__init__(title="📝 Contenido del Buzón Gremial")

        # Campo 1: Clasificación limpia mediante texto corto
        self.add_item(
            discord.ui.InputText(
                label="Tipo de envío (Petición / Queja / Sugerencia)",
                placeholder="Ej: Petición, Queja, Sugerencia...",
                required=True,
                max_length=20
            )
        )

        # Campo 2: Cuerpo del mensaje detallado
        self.add_item(
            discord.ui.InputText(
                label="Contenido del Comentario",
                placeholder="Redacta de forma detallada tu feedback aquí...",
                style=discord.InputTextStyle.long,
                required=True,
                max_length=1000
            )
        )

    async def callback(self, interaction: discord.Interaction):
        # Handshake inmediato para blindar la interacción contra el error 10062 de la API
        await interaction.response.defer(ephemeral=True)
        
        guild = interaction.guild
        if not guild: 
            return

        canal_destino = guild.get_channel(config.CANAL_BUZON_SECRETARIA)
        if not canal_destino:
            await interaction.followup.send("❌ Error Crítico: El canal del buzón secretaria no fue localizado en la configuración.", ephemeral=True)
            return

        tipo = self.children[0].value.strip().upper()
        contenido = self.children[1].value.strip()
        folio = random.randint(1000, 9999)

        # Construcción estética y segura del Embed institucional
        embed = discord.Embed(
            title=f"📥 REQUISICIÓN RECIBIDA • FOLIO #{folio}",
            color=discord.Color.dark_gray() if self.es_anonimo else discord.Color.teal()
        )
        embed.add_field(name="📌 Clasificación", value=f"`{tipo}`", inline=True)
        embed.add_field(name="🔒 Anonimato", value="`CONFIDENCIAL`" if self.es_anonimo else "`REVELADO`", inline=True)
        embed.add_field(name="📝 Mensaje", value=contenido, inline=False)

        # Capa de anonimización irreversible controlada por la arquitectura del software
        if self.es_anonimo:
            embed.set_footer(text="Seguridad Gremial • Los metadatos de usuario han sido purgados de la transmisión.")
        else:
            embed.add_field(name="👤 Remitente Oficial", value=f"{interaction.user.mention} (ID: {interaction.user.id})", inline=False)
            embed.set_footer(text="Seguridad Gremial • Identidad revelada a petición del jugador.")

        # Inyección limpia en el canal restringido de la Directiva
        await canal_destino.send(embed=embed)

        # Confirmación efímera al usuario
        mensaje_confirmacion = f"✅ **Envío Exitoso (Folio #{folio}):** Tu comentario ha sido depositado en el Archivo Secreto.\n"
        if self.es_anonimo:
            mensaje_confirmacion += "Tu identidad fue purgada con éxito; nadie en el Staff sabrá quién envió este pergamino."
        else:
            mensaje_confirmacion += "Has decidido compartir tu nombre; el Staff podrá contactarte de ser necesario."

        await interaction.followup.send(mensaje_confirmacion, ephemeral=True)


class SelectorModalidadBuzon(discord.ui.View):
    """Mensaje efímero intermedio que actúa como filtro binario infalible para el anonimato."""
    def __init__(self):
        super().__init__(timeout=60) # Timeout corto para limpiar componentes efímeros

    @discord.ui.button(label="🔒 Enviar de Forma Anónima", style=discord.ButtonStyle.danger)
    async def opcion_anonima(self, button: discord.ui.Button, interaction: discord.Interaction):
        # Desplegamos el modal inyectando True en el control de anonimato
        await interaction.response.send_modal(FormularioContenidoBuzon(es_anonimo=True))
        self.stop()

    @discord.ui.button(label="👤 Enviar Revelando Identidad", style=discord.ButtonStyle.primary)
    async def opcion_revelada(self, button: discord.ui.Button, interaction: discord.Interaction):
        # Desplegamos el modal inyectando False en el control de anonimato
        await interaction.response.send_modal(FormularioContenidoBuzon(es_anonimo=False))
        self.stop()


class BotonBuzon(discord.ui.View):
    """Botón estático permanente colocado en el canal público."""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📝 Enviar Comentario / Queja", style=discord.ButtonStyle.secondary, custom_id="btn_desplegar_buzon")
    async def desplegar_callback(self, button: discord.ui.Button, interaction: discord.Interaction):
        # En lugar de lanzar un modal directo e inseguro, enviamos el filtro efímero intermedio
        await interaction.response.send_message(
            "🔒 **FILTRO DE PRIVACIDAD:** Selecciona cómo deseas que el Staff reciba tu requisición en las oficinas de la Secretaría:",
            view=SelectorModalidadBuzon(),
            ephemeral=True
        )


class BuzonCog(commands.Cog):
    """Módulo encargado de gestionar el buzón transaccional de feedback institucional."""
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        # Registrar la vista raíz para que el botón sea 100% persistente tras los reinicios del bot
        self.bot.add_view(BotonBuzon())

    @commands.slash_command(name="setup_buzon", description="[STAFF] Inicializa el botón fijo del buzón en un canal público.")
    async def setup_buzon(self, ctx: discord.ApplicationContext):
        if not any(rol.id in config.ROLES_CLAUSURA for rol in ctx.user.roles):
            await ctx.respond("❌ No tienes autorización de rango alto para desplegar este portal.", ephemeral=True)
            return

        embed = discord.Embed(
            title="🏛️ ALTAVOZ DEL PUEBLO • BUZÓN GREMIAL",
            description="Usa este canal para hacer llegar tus sugerencias, quejas, peticiones o reclamos a la Directiva del Gremio.\n\n"
                        "💡 **¿Cómo funciona?**\n"
                        "Al presionar el botón de abajo, se abrirá un menú de selección privado. "
                        "Tú decides con total seguridad si deseas mantener el anonimato confidencial o revelar tu identidad al Staff para recibir una respuesta formal.",
            color=discord.Color.dark_magenta()
        )
        
        await ctx.channel.send(embed=embed, view=BotonBuzon())
        await ctx.respond("Portal del buzón inicializado correctamente.", ephemeral=True)

def setup(bot):
    bot.add_cog(BuzonCog(bot))
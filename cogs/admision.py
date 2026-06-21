# cogs/admision.py

import discord
from discord.ext import commands
import config
import database  # Consumo exclusivo del pool de persistencia centralizado
import re
import asyncio
from utils.nivel20_scraper import extraer_datos_nivel20

class SelectLadder(discord.ui.Select):
    """Menú de selección interactivo para conmutar las pestañas del Ladder."""
    def __init__(self):
        options = [
            discord.SelectOption(label="Clasificación: Guerreros de Midgard", description="Top 10 héroes del reino por nivel de personaje.", emoji="🛡️", value="aventureros"),
            discord.SelectOption(label="Clasificación: Skalds", description="Top 10 narradores por campaigns dirigidas.", emoji="🎲", value="dms")
        ]
        super().__init__(placeholder="Elige la pestaña del Salón de la Fama...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        embed_actualizado = discord.Embed(color=discord.Color.gold())
        
        if self.values[0] == "aventureros":
            embed_actualizado.title = "🏆 SALÓN DE LA FAMA: CLASIFICACIÓN DE GUERREROS"
            embed_actualizado.description = "Matrícula oficial de los 10 personajes con mayor progresión en campaña:\n\n"
            datos = await database.obtener_ladder_aventureros()
            if not datos:
                embed_actualizado.description += "*No se registran héroes inscritos en los archivos.*"
            else:
                for i, (uid, name, nivel, sesiones) in enumerate(datos, 1):
                    embed_actualizado.description += f"**#{i}** | <@{uid}> (`{name}`) — **Nivel {nivel}** ({sesiones} misiones cumplidas)\n"
        else:
            embed_actualizado.title = "🔮 CONCILIO DE NARRADORES: CLASIFICACIÓN DE SKALDS"
            embed_actualizado.description = "Registro maestro de los 10 Skalds con mayor volumen de arbitraje:\n\n"
            datos = await database.obtener_ladder_dms()
            if not datos:
                embed_actualizado.description += "*No se registran Skalds en el registro operativo.*"
            else:
                for i, (nombre, licencia, partidas, aprobacion) in enumerate(datos, 1):
                    embed_actualizado.description += f"**#{i}** | **{nombre}** [{licencia}] — **{partidas} sesiones** (👍 {aprobacion}% aprobación real)\n"
                    
        embed_actualizado.set_footer(text="Estadísticas de control maestro actualizadas en tiempo real.")
        await interaction.edit_original_response(embed=embed_actualizado)


class LadderView(discord.ui.View):
    """Contenedor de la vista del Ladder."""
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(SelectLadder())


class ModalEditarFicha(discord.ui.Modal):
    """Formulario emergente interactivo para la corrección manual de datos biográficos."""
    def __init__(self, usuario: discord.Member, datos_actuales):
        super().__init__(title=f"Editar Ficha: {usuario.name}")
        self.usuario = usuario

        self.add_item(discord.ui.InputText(label="Nombre del Personaje", value=datos_actuales[0], max_length=100))
        self.add_item(discord.ui.InputText(label="Raza", value=datos_actuales[1], max_length=50))
        self.add_item(discord.ui.InputText(label="Clase", value=datos_actuales[2], max_length=50))
        self.add_item(discord.ui.InputText(label="Edad", value=str(datos_actuales[3]), max_length=15))
        self.add_item(discord.ui.InputText(label="Estatura (ej: 1.75m)", value=datos_actuales[4], max_length=50))

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        nombre = self.children[0].value.strip()
        raza = self.children[1].value.strip()
        clase = self.children[2].value.strip()
        edad_str = self.children[3].value.strip()
        estatura = self.children[4].value.strip()

        try:
            edad = int(edad_str)
        except ValueError:
            await interaction.followup.send("❌ La edad debe ser un número entero válido.", ephemeral=True)
            return

        ficha_vieja = await database.obtener_personaje(self.usuario.id)
        link_original = ficha_vieja[5] if ficha_vieja else "https://nivel20.com"

        await database.editar_datos_personaje(self.usuario.id, nombre, raza, clase, edad, estatura, link_original)
        
        embed = discord.Embed(title="📝 MATRÍCULA MODIFICADA EXITOSAMENTE", color=discord.Color.teal())
        embed.add_field(name="🛡️ Nombre", value=nombre, inline=True)
        embed.add_field(name="🧬 Raza / Clase", value=f"{raza} / {clase}", inline=True)
        embed.add_field(name="🎂 Edad / Estatura", value=f"{edad} años / {estatura}", inline=True)
        embed.set_footer(text=f"Cambios aplicados por la Autoridad: {interaction.user.name}")
        await interaction.followup.send(embed=embed)


class ConfirmacionRegistro(discord.ui.View):
    """Botonera final de confirmación en texto plano."""
    def __init__(self, oficial_id, usuario_target, datos_ficha):
        super().__init__(timeout=300)
        self.oficial_id = oficial_id
        self.usuario_target = usuario_target
        self.datos = datos_ficha

    @discord.ui.button(label="Confirmar Registro", style=discord.ButtonStyle.success, custom_id="btn_confirmar_reg")
    async def confirmar(self, button: discord.ui.Button, interaction: discord.Interaction):
        if interaction.user.id != self.oficial_id:
            await interaction.response.send_message("❌ Solo el personal del gremio que inició el comando puede confirmar.", ephemeral=True)
            return

        await interaction.response.defer()
        
        await database.registrar_personaje(
            self.usuario_target.id, 
            self.datos["nombre"], 
            self.datos["raza"], 
            self.datos["clase"], 
            self.datos["edad"], 
            self.datos["estatura"], 
            self.datos["link"]
        )

        # NUEVO FLUJO: Extracción Automática en la Admisión
        link_nivel20 = self.datos["link"].strip()
        if link_nivel20.startswith("http"):
            try:
                datos_extraidos = await extraer_datos_nivel20(link_nivel20)
                if datos_extraidos:
                    await database.guardar_datos_ficha_nivel20(self.usuario_target.id, datos_extraidos)
            except Exception as e:
                print(f"Error extrayendo datos en registro para {self.usuario_target.name}: {e}")

        rol_aventurero = interaction.guild.get_role(config.ROL_AVENTURERO)
        rol_viajero = interaction.guild.get_role(config.ROL_VIAJERO)
        
        if rol_aventurero: await self.usuario_target.add_roles(rol_aventurero)
        if rol_viajero: await self.usuario_target.remove_roles(rol_viajero)

        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)

        await interaction.channel.send("✅ **REGISTRO CORRECTO:** Personaje asentado en los libros del Gremio. Eliminando canal en 5 segundos...")
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete()
        except discord.NotFound:
            # BLINDAJE: Si otro mod borra el canal a mano antes de que pasen los 5 segundos.
            pass
        except discord.Forbidden:
            print("⚠️ No tengo permisos para borrar este canal de ticket.")

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.danger, custom_id="btn_cancelar_reg")
    async def cancelar(self, button: discord.ui.Button, interaction: discord.Interaction):
        if interaction.user.id != self.oficial_id:
            await interaction.response.send_message("❌ Solo el personal del gremio que inició el comando puede cancelar.", ephemeral=True)
            return

        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)
        await interaction.response.send_message(f"❌ Registro cancelado por {interaction.user.mention}.")
        self.stop()


# 🏛️ COG REESTRUCTURADO: MOTOR DE ESCUCHA PASIVA POR EVENTO GLOBAL

class AdmisionCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Memoria RAM transitoria para rastrear qué ticket pertenece a qué Oficial y Aspirante
        # Estructura: { canal_id: (oficial_id, usuario_target_objeto) }
        self.sesiones_activas = {}

    @commands.slash_command(name="aprobar_ficha", description="[OFFICIAL] Envía la plantilla de texto plano al chat para su rellenado.")
    async def aprobar_ficha(self, ctx: discord.ApplicationContext, usuario: discord.Option(discord.Member, "Selecciona al Viajero a registrar")):
        """Envía la plantilla clásica al chat. No bloquea el loop ni levanta ventanas."""
        if not any(rol.id in config.ROLES_APROBACION for rol in ctx.user.roles):
            await ctx.respond("❌ No tienes el rango de Oficial Gremial o superior para ejecutar este proceso.", ephemeral=True)
            return

        ficha_existente = await database.obtener_personaje(usuario.id)
        if int(config.ROL_AVENTURERO) in [r.id for r in usuario.roles] or ficha_existente:
            embed = discord.Embed(
                title="❌ ERROR: JUGADOR YA REGISTRADO",
                description=f"El guerrero {usuario.mention} **YA** tiene un personaje activo o el rol de Guerrero asignado.",
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed)
            return

        plantilla = (
            f"📋 **PLANTILLA DE REGISTRO OFICIAL**\n"
            f"Oficial a cargo: {ctx.user.mention} | Registrando a: {usuario.mention}\n"
            f"Nombre: \n"
            f"Raza: \n"
            f"Clase: \n"
            f"Edad: \n"
            f"Estatura: \n"
            f"Link: \n"
            f"\n"
            f"⚠️ **INSTRUCCIONES:** Copia el bloque anterior, rellena los datos en texto plano y envíalo a este chat. "
            f"Asegúrate de mantener intactas las palabras clave seguidas de los dos puntos (:)."
        )
        
        # Guardamos en el diccionario de la RAM que este canal espera una plantilla de este Oficial
        self.sesiones_activas[ctx.channel.id] = (ctx.user.id, usuario)

        await ctx.respond("Instrucción enviada al ticket.", ephemeral=True)
        await ctx.channel.send(plantilla)


    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Escuchador pasivo global de alto rendimiento. Captura la plantilla en el chat sin wait_for."""
        # Filtro 1: Ignorar si el mensaje proviene de un bot o si el canal no está esperando una admisión activa
        if message.author.bot or message.channel.id not in self.sesiones_activas:
            return

        # Recuperar la metadata de la sesión guardada en RAM
        oficial_id, usuario_target = self.sesiones_activas[message.channel.id]

        # Filtro 2: El mensaje debe ser del Oficial a cargo y debe empezar estrictamente con el formato requerido
        if message.author.id != oficial_id or not message.content.strip().startswith("Nombre:"):
            return

        # El bot detectó la plantilla rellena. Procedemos al procesamiento asíncrono seguro
        content = message.content
        try:
            # BLINDAJE REGEX: Usar regex es útil, pero si el usuario no pone el espacio o usa un formato
            # ligeramente distinto en celular, crasheará. Las regex actuales en tu código son robustas,
            # pero atrapamos el error si no hacen match para no matar el event loop.
            nombre = re.search(r"Nombre:\s*(.*)", content).group(1).strip()
            raza = re.search(r"Raza:\s*(.*)", content).group(1).strip()
            clase = re.search(r"Clase:\s*(.*)", content).group(1).strip()
            edad_str = re.search(r"Edad:\s*(.*)", content).group(1).strip()
            estatura = re.search(r"Estatura:\s*(.*)", content).group(1).strip()
            link = re.search(r"Link:\s*(.*)", content).group(1).strip()
            
            edad = int(edad_str)
            if not (nombre and raza and clase and estatura and link):
                raise ValueError("Faltan datos obligatorios")
        except AttributeError:
            # Si un Regex falla (retorna None), el .group(1) lanza AttributeError
            await message.channel.send("❌ **ERROR DE REGISTRO:** Estructura corrupta. Asegúrate de rellenar TODOS los campos correctamente detrás de cada dos puntos (:).")
            return
        except ValueError:
            # Si la edad no es un número entero
            await message.channel.send("❌ **ERROR DE REGISTRO:** La edad debe ser un número entero.")
            return
        except Exception as e:
            await message.channel.send(f"❌ **ERROR INESPERADO:** {e}")
            return

        # Purgamos el canal de la RAM de sesiones activas ya que el objetivo fue capturado
        del self.sesiones_activas[message.channel.id]

        # Instanciar vista de confirmación tradicional
        view = ConfirmacionRegistro(oficial_id, usuario_target, {"nombre": nombre, "raza": raza, "clase": clase, "edad": edad, "estatura": estatura, "link": link})
        
        embed_review = discord.Embed(title="🔍 VALIDACIÓN DE MATRÍCULA", description="Revisa que los datos capturados en el chat sean correctos.", color=discord.Color.gold())
        embed_review.add_field(name="Nombre", value=nombre, inline=True)
        embed_review.add_field(name="Raza / Clase", value=f"{raza} / {clase}", inline=True)
        embed_review.add_field(name="Edad / Estatura", value=f"{edad} años / {estatura}", inline=True)
        embed_review.add_field(name="Link Ficha", value=link, inline=False)
        
        await message.channel.send(embed=embed_review, view=view)


    @commands.slash_command(name="eliminar_ficha", description="[MANAGEMENT] Purga el personaje de un Guerrero.")
    async def eliminar_ficha(self, ctx: discord.ApplicationContext, usuario: discord.Option(discord.Member, "Guerrero al cual borrarle la ficha")):
        if not any(rol.id in config.ROLES_CLAUSURA for rol in ctx.user.roles):
            await ctx.respond("❌ Exclusivo para la alta gerencia (Supervisores o Jefes Gremiales).", ephemeral=True)
            return

        exito = await database.eliminar_personaje(usuario.id)
        if exito:
            rol_aventurero = ctx.guild.get_role(config.ROL_AVENTURERO)
            if rol_aventurero and rol_aventurero in usuario.roles:
                await usuario.remove_roles(rol_aventurero)
            await ctx.respond(f"🧹 ✅ **REGISTRO ELIMINADO:** La ficha de {usuario.mention} ha sido purgada.")
        else:
            await ctx.respond(f"❌ Error: El usuario no posee ninguna ficha registrada.", ephemeral=True)

    @commands.slash_command(name="subir_nivel", description="[STAFF] Incrementa el nivel oficial de un Guerrero de Midgard.")
    async def subir_nivel(self, ctx: discord.ApplicationContext, usuario: discord.Option(discord.Member, "Selecciona al Guerrero"), modificador: int):
        if not any(rol.id in config.ROLES_EDICION_MATRICULA for rol in ctx.user.roles):
            await ctx.respond("❌ **Acceso Denegado.**", ephemeral=True)
            return
        ficha = await database.obtener_personaje(usuario.id)
        if not ficha: 
            await ctx.respond("❌ El usuario no tiene un personaje registrado.", ephemeral=True)
            return
            
        nuevo = ficha[-1] + modificador
        await database.actualizar_nivel_personaje(usuario.id, nuevo)
        await ctx.respond(f"📈 Nivel de {usuario.mention} actualizado a {nuevo}.")

    @commands.slash_command(name="set_nivel", description="[STAFF] Sobreescribe y fija el nivel exacto.")
    async def set_nivel(self, ctx: discord.ApplicationContext, usuario: discord.Option(discord.Member, "Guerrero"), nivel_fijo: int):
        if not any(rol.id in config.ROLES_EDICION_MATRICULA for rol in ctx.user.roles):
            await ctx.respond("❌ **Acceso Denegado.**", ephemeral=True)
            return
        await database.actualizar_nivel_personaje(usuario.id, nivel_fijo)
        await ctx.respond(f"🔧 Nivel fijado en {nivel_fijo} para {usuario.mention}.")

    @commands.slash_command(name="editar_ficha", description="[HIGH STAFF] Modifica datos biográficos.")
    async def editar_ficha(self, ctx: discord.ApplicationContext, usuario: discord.Option(discord.Member, "Guerrero")):
        if not any(rol.id in config.ROLES_EDICION_MATRICULA for rol in ctx.user.roles):
            await ctx.respond("❌ **Acceso Denegado.**", ephemeral=True)
            return
        ficha = await database.obtener_personaje(usuario.id)
        if not ficha: 
            await ctx.respond("❌ El usuario no tiene un personaje registrado.", ephemeral=True)
            return
        await ctx.send_modal(ModalEditarFicha(usuario, ficha))

    @commands.slash_command(name="perfil_dm", description="[PRIVATE] Muestra la acreditación, reputación y volumen de arbitraje de un Skald.")
    async def perfil_dm(self, ctx: discord.ApplicationContext, usuario: discord.Option(discord.Member, "Selecciona al Skald a consultar", default=None)):
        target_user = usuario or ctx.user
        perfil = await database.obtener_perfil_dm(target_user.id)
        if not perfil:
            await ctx.respond(f"❌ El usuario {target_user.mention} no registra una matrícula de Skald activa en el sistema.", ephemeral=True)
            return

        licencia = perfil["licencia"].upper()
        restriccion = "Nivel 1-2 [Restricción Básica de Aprendiz]"
        if "EXPERTO" in licencia:
            restriccion = "Nivel 1-6 [Restricción Avanzada de Campaña]"
        elif "OFICIAL" in licencia or "VETERANO" in licencia:
            restriccion = "Sin Restricción [Nivel Libre Absoluto]"

        estatus = "Estatus Neutral"
        if perfil["aprobacion"] >= 85: estatus = "🏅 Excelente Estatus Gremial"
        elif perfil["aprobacion"] < 50: estatus = "⚠️ Alerta / Revisión Inmediata de Licencia"

        embed = discord.Embed(
            title="🛡️ GREMIO DE GUERREROS - CERTIFICACIÓN OFICIAL",
            description=f"Documento Maestro expedido de forma privada para validar las facultades de arbitraje de la autoridad gremial.",
            color=discord.Color.dark_purple()
        )
        embed.add_field(name="👤 Skald", value=target_user.mention, inline=True)
        embed.add_field(name="🎖️ Rango de Licencia", value=f"`{perfil['licencia']}`", inline=True)
        embed.add_field(name="📜 Registro de Campañas", value=f"├ 🎲 **Narradas:** `{perfil['partidas']} sesiones`\n└ 🎭 **Límite:** `{restriccion}`", inline=False)
        embed.add_field(name="⚖️ Reputación del Concilio", value=f"├ ⭐ **Aprobación:** `{perfil['aprobacion']}%` *(Votos válidos: {perfil['total_validas']})*\n└ 💬 **Estatus:** `{estatus}`", inline=False)
        embed.set_footer(text="Acreditación Gremial - Emisión Privada y Efímera")

        await ctx.respond(embed=embed, ephemeral=True)

    @commands.slash_command(name="setup_ladder", description="[HIGH STAFF] Despliega el panel de clasificación dinámico e interactivo del Gremio.")
    async def setup_ladder(self, ctx: discord.ApplicationContext):
        if not any(rol.id in [1509952429586780332, 1509954249436696758] for rol in ctx.user.roles):
            await ctx.respond("❌ **Acceso Denegado:** Comando exclusivo para la Alta Directiva Suprema del Gremio.", ephemeral=True)
            return

        embed = discord.Embed(
            title="🏆 SALÓN DE LA FAMA - TABLAS DE CLASIFICACIÓN",
            description="Utiliza el menú desplegable de abajo para navegar de forma dinámica entre las estadísticas de los Guerreros más condecorados y los Skalds con mayor trayectoria del reino.",
            color=discord.Color.gold()
        )
        embed.set_footer(text="Gremio de Guerreros - Sistema de Clasificación Fijo")
        
        await ctx.send(embed=embed, view=LadderView())
        await ctx.respond("✅ El panel dinámico del Ladder ha sido inicializado con éxito.", ephemeral=True)

    @commands.slash_command(name="escanear_ficha", description="[STAFF] Extrae y sincroniza la hoja de personaje de Nivel20.")
    async def escanear_ficha(self, ctx: discord.ApplicationContext, link_nivel20: discord.Option(str, "Link de la ficha en Nivel20 (https://nivel20.com/...)"), usuario: discord.Option(discord.Member, "Jugador al que pertenece (por defecto tú)", required=False) = None):
        """Herramienta de diagnóstico e importación manual para leer Nivel20."""
        # Restricción de Staff
        if not any(rol.id in config.ROLES_APROBACION for rol in ctx.user.roles):
            await ctx.respond("❌ Solo los Oficiales pueden ejecutar escaneos manuales.", ephemeral=True)
            return

        target_user = usuario or ctx.user

        await ctx.defer() # Porque el scraping puede tardar unos segundos

        # 1. Scraping
        datos_extraidos = await extraer_datos_nivel20(link_nivel20)
        if not datos_extraidos:
            await ctx.followup.send("❌ Error al intentar leer la ficha de Nivel20. Revisa que el enlace sea correcto y la ficha sea pública.")
            return

        # 2. Guardar en Base de Datos de forma persistente
        # Solo lo guardamos si el usuario ya existe en "aventureros" para no romper Foreign Keys.
        ficha_existente = await database.obtener_personaje(target_user.id)
        if not ficha_existente:
             await ctx.followup.send(f"⚠️ El usuario {target_user.mention} no está registrado como Guerrero en la base de datos central. ¡No se pudo guardar la sincronización! Deberían pasar por el ticket primero.")
             return

        await database.guardar_datos_ficha_nivel20(target_user.id, datos_extraidos)

        # 3. Formateo y Resumen del Reporte
        embed = discord.Embed(
            title="🔍 FICHA ESCANEADA Y SINCRONIZADA",
            description=f"Datos extraídos exitosamente de Nivel20 para {target_user.mention}.",
            color=discord.Color.green()
        )

        # Stats
        stats_str = (
            f"**FUE:** {datos_extraidos['fuerza']} | **DES:** {datos_extraidos['destreza']} | **CON:** {datos_extraidos['constitucion']}\n"
            f"**INT:** {datos_extraidos['inteligencia']} | **SAB:** {datos_extraidos['sabiduria']} | **CAR:** {datos_extraidos['carisma']}\n"
            f"**Iniciativa:** {datos_extraidos['iniciativa']} | **Velocidad:** {datos_extraidos['velocidad']} | **Competencia:** {datos_extraidos['competencia']}"
        )
        embed.add_field(name="Atributos de Combate", value=stats_str, inline=False)

        # Clases
        clases_str = "\n".join([f"• {c['nombre']} (Nv. {c['nivel']})" for c in datos_extraidos['clases']]) or "Ninguna detectada"
        embed.add_field(name="Clases", value=clases_str, inline=True)

        # Conjuros
        conjuros_str = "\n".join([f"• {s['nombre']} ({s['nivel']})" for s in datos_extraidos['conjuros']])
        if len(conjuros_str) > 1000:
            conjuros_str = conjuros_str[:1000] + "\n... (Y más)"
        embed.add_field(name="Conjuros", value=conjuros_str or "Ninguno detectado", inline=True)

        # Equipo
        equipo_str = "\n".join([f"• {i}" for i in datos_extraidos['equipo']])
        if len(equipo_str) > 1000:
            equipo_str = equipo_str[:1000] + "\n... (Y más)"
        embed.add_field(name="Inventario Sincronizado", value=equipo_str or "Vacío", inline=False)

        await ctx.followup.send(embed=embed)

    @commands.slash_command(name="setup_admision", description="[STAFF] Despliega el botón fijo para la apertura de tickets de admisión.")
    async def setup_admision(self, ctx: discord.ApplicationContext):
        if not any(rol.id in config.ROLES_CLAUSURA for rol in ctx.user.roles):
            await ctx.respond("❌ No tienes autorización de rango alto para desplegar este panel.", ephemeral=True)
            return
            
        from cogs.tickets import TicketBotonera
        embed = discord.Embed(title="📜 REGISTRO DE NUEVOS GUERREROS", description="Presiona el botón de abajo para abrir un canal privado de revisión e iniciar la validación de tu ficha de personaje.", color=discord.Color.blue())
        embed.set_footer(text="Gremio de Guerreros - Sistema de Admisiones")
        await ctx.send(embed=embed, view=TicketBotonera())
        await ctx.respond("✅ Panel de admisión desplegado con éxito.", ephemeral=True)

def setup(bot):
    bot.add_cog(AdmisionCog(bot))
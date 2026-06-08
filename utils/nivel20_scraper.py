import aiohttp
from bs4 import BeautifulSoup
import re
import asyncio

async def extraer_datos_nivel20(url: str) -> dict:
    """
    Descarga y raspa la página de Nivel20 del enlace provisto para obtener
    las estadísticas de combate, clases, equipo, conjuros y rasgos.
    """
    from urllib.parse import urlparse

    # Validación estricta de seguridad: Evitar SSRF
    try:
        parsed_url = urlparse(url)
        if parsed_url.hostname not in ('nivel20.com', 'www.nivel20.com'):
            return None
    except Exception:
        return None

    # Expresiones regulares para los links de los atributos
    regex_atributos = {
        'fue': re.compile(r'edit_custom\?.*field=fue.*current_value=([0-9]+)'),
        'des': re.compile(r'edit_custom\?.*field=des.*current_value=([0-9]+)'),
        'con': re.compile(r'edit_custom\?.*field=con.*current_value=([0-9]+)'),
        'int': re.compile(r'edit_custom\?.*field=int.*current_value=([0-9]+)'),
        'sab': re.compile(r'edit_custom\?.*field=sab.*current_value=([0-9]+)'),
        'car': re.compile(r'edit_custom\?.*field=car.*current_value=([0-9]+)'),
        'iniciativa': re.compile(r'edit_custom\?.*field=initiative.*current_value=(%2B[0-9]+|-?[0-9]+)'),
        'competencia': re.compile(r'edit_custom\?.*field=proficiency_bonus.*current_value=(%2B[0-9]+|-?[0-9]+)'),
        'velocidad': re.compile(r'edit_custom\?.*field=speed.*current_value=.*?%3E([0-9]+)%3C') # Puede requerir decode si viene como %3E30%3C
    }

    # Estructura del diccionario a retornar
    datos_extraidos = {
        'fuerza': 10,
        'destreza': 10,
        'constitucion': 10,
        'inteligencia': 10,
        'sabiduria': 10,
        'carisma': 10,
        'iniciativa': '+0',
        'competencia': '+2',
        'velocidad': '30 pies',
        'clases': [],      # [{'nombre': 'Hechicero', 'nivel': 1}]
        'rasgos': [],      # ['Visión en la oscuridad', ...]
        'conjuros': [],    # [{'nombre': 'Bola de Fuego', 'nivel': 'Nivel 3'}]
        'equipo': []       # ['Foco arcano', 'Espada corta']
    }

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            # Seguimos las redirecciones automáticas (importante para links cortos /s/)
            async with session.get(url, allow_redirects=True, timeout=10) as response:
                if response.status != 200:
                    return None

                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')

                # ==========================================
                # 1. ATRIBUTOS (Stats, Iniciativa, etc)
                # Buscamos en todos los divs con atributos `data-remote`
                # ==========================================
                for div in soup.find_all(attrs={"data-remote": True}):
                    data_remote = div['data-remote']

                    # Fuerza
                    m = regex_atributos['fue'].search(data_remote)
                    if m: datos_extraidos['fuerza'] = int(m.group(1))

                    m = regex_atributos['des'].search(data_remote)
                    if m: datos_extraidos['destreza'] = int(m.group(1))

                    m = regex_atributos['con'].search(data_remote)
                    if m: datos_extraidos['constitucion'] = int(m.group(1))

                    m = regex_atributos['int'].search(data_remote)
                    if m: datos_extraidos['inteligencia'] = int(m.group(1))

                    m = regex_atributos['sab'].search(data_remote)
                    if m: datos_extraidos['sabiduria'] = int(m.group(1))

                    m = regex_atributos['car'].search(data_remote)
                    if m: datos_extraidos['carisma'] = int(m.group(1))

                    m = regex_atributos['iniciativa'].search(data_remote)
                    if m:
                        val = m.group(1).replace('%2B', '+')
                        datos_extraidos['iniciativa'] = val

                    m = regex_atributos['competencia'].search(data_remote)
                    if m:
                        val = m.group(1).replace('%2B', '+')
                        datos_extraidos['competencia'] = val

                    m = regex_atributos['velocidad'].search(data_remote)
                    if m:
                        datos_extraidos['velocidad'] = m.group(1) + " pies"


                # ==========================================
                # 2. CLASES Y NIVELES
                # La metaetiqueta og:description tiene algo como:
                # "¡Mira mi personaje en Nivel20! Semielfo Hechicero 1, Bardo 2"
                # ==========================================
                meta_desc = soup.find('meta', property='og:description')
                if meta_desc and meta_desc.get('content'):
                    content = meta_desc['content']
                    # Extraer las clases usando regex.
                    # Rompemos por la palabra clave "!" para aislar "Semielfo Hechicero 1, Bardo 2"
                    parts = content.split('! ')
                    if len(parts) > 1:
                        # parts[1] seria "Semielfo Hechicero 1, Bardo 2"
                        class_part = parts[1]

                        # Separar raza de las clases es difícil sin saber las razas.
                        # Pero podemos buscar el patrón "Palabra Numero" (ej: "Hechicero 1")
                        clases_match = re.findall(r'([A-Za-zñÑáéíóúÁÉÍÓÚ\s]+)\s+([0-9]+)', class_part)
                        for c_nombre, c_nivel in clases_match:
                            # Puede que la primera clase traiga la raza pegada (ej: "Semielfo Hechicero")
                            # Tomamos solo la ultima palabra como clase en ese caso.
                            # Para algo más "seguro", solo limpiamos espacios
                            c_nombre_limpio = c_nombre.strip().split()[-1]

                            datos_extraidos['clases'].append({
                                'nombre': c_nombre_limpio,
                                'nivel': int(c_nivel)
                            })

                # ==========================================
                # 3. EQUIPO E INVENTARIO
                # Los ítems suelen estar en listados. Generalmente los nombres de items
                # están bajo clases que representan los ítems en el inventario.
                # ==========================================

                # Usaremos la clase `accordion-title` que Nivel20 usa para listar los ítems del inventario
                # (y armas, armaduras). Aparece dentro de `<span class='accordion-title'>`.
                # Primero limitamos la búsqueda solo a la sección del inventario para no traer basura.
                # Pero si no, buscamos globalmente descartando palabras clave reservadas.
                palabras_ignoradas_equipo = ['Equipado', 'Otros', 'Monedas', 'Ataques']

                # Iteramos sobre todos los spans que tienen accordion-title (generalmente usados en el panel colapsable del equipo)
                # Ojo: esto también puede capturar conjuros o rasgos si están formateados igual.
                # Nivel20 suele tener los ítems bajo el div "collapse_items"
                # Aunque div_items puede servir, la estructura a veces separa el inventario en varios paneles colapsables
                # Mejor buscamos todos los acordeones que estén bajo la pestaña de inventario (su contenedor suele tener ids o clases genéricas)
                # O simplemente buscamos por todo el HTML
                for span in soup.find_all('span', class_='accordion-title'):
                    nombre_item = span.get_text(strip=True)
                    if nombre_item and nombre_item not in palabras_ignoradas_equipo:
                        # Para evitar meter nombres de Rasgos o Acciones como equipo, filtramos viendo el div contenedor
                        # Nivel20 envuelve los items en un div de "items"
                        parent = span.find_parent('div', id='collapse_items')
                        if parent:
                            if nombre_item not in datos_extraidos['equipo']:
                                datos_extraidos['equipo'].append(nombre_item)

                # ==========================================
                # 4. CONJUROS
                # En la pestaña de conjuros, los hechizos listados tienen la clase "spell-row"
                # y el nombre suele estar en data-floating-title o dentro del contenido
                # ==========================================
                for spell_a in soup.find_all('a', class_=lambda c: c and 'spell-row' in c):
                    nombre_spell = spell_a.get('data-floating-title')
                    if not nombre_spell:
                        # Fallback por si no tiene ese atributo
                        strong_tag = spell_a.find('strong')
                        if strong_tag:
                            nombre_spell = strong_tag.get_text(strip=True)

                    if nombre_spell:
                        # El nivel suele estar en un div hermano al strong, podemos buscar palabras como "Truco" o "Nv." o "Nivel X"
                        nivel = "?"
                        divs = spell_a.find_all('div')
                        for d in divs:
                            txt = d.get_text(strip=True)
                            if txt.lower() == 'truco' or txt.lower().startswith('nv.'):
                                nivel = txt
                                break

                        # Nivel20 carga listas de hechizos de toda la clase.
                        # Solo queremos los preparados/conocidos.
                        # Nivel20 usa el botón btn-toggle button-add con clase "active" para los aprendidos.
                        btn = spell_a.find('button', class_='button-add')
                        if btn and 'active' in btn.get('class', []):
                            if not any(s['nombre'] == nombre_spell for s in datos_extraidos['conjuros']):
                                datos_extraidos['conjuros'].append({
                                    'nombre': nombre_spell,
                                    'nivel': nivel
                                })

                # ==========================================
                # 5. RASGOS (Features)
                # Rasgos suelen estar bajo href="?panel=features..."
                # ==========================================
                for feat_a in soup.find_all('a', href=re.compile(r'\?panel=features')):
                    nombre_feat = feat_a.get_text(strip=True)
                    nombre_feat = nombre_feat.split('\n')[0].strip()
                    if nombre_feat and nombre_feat not in datos_extraidos['rasgos']:
                        datos_extraidos['rasgos'].append(nombre_feat)


                # ==========================================
                # 6. ESPACIOS DE CONJUROS
                # ==========================================
                # Vamos a capturar el HTML de los espacios de conjuro
                # Aparecen como "Espacios de conjuro" o similar, o en un contenedor con .spell-slots
                # Si el usuario tiene una tabla o inputs con data-max, podríamos intentar leerlos,
                # pero puede ser complicado de parsear de forma genérica.
                # Como extra, busquemos algo simple: div class "spell-slots" o similar.
                # (Lo dejaremos básico por ahora, Nivel20 usa cajas numéricas que a veces están ocultas)

        # Validación final de integridad: si no extrajo ninguna clase, es probable que la página estuviera vacía o mal formada.
        if not datos_extraidos['clases']:
             return None

        return datos_extraidos
    except Exception as e:
        print(f"Error raspando Nivel20: {e}")
        return None

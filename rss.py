import re
import urllib.request
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from urllib.parse import urljoin


BASE_URL = "https://www.logista.com"

PAGINA_PRINCIPAL = (
    "https://www.logista.com/es/home/"
    "media/press-releases.html"
)

ARCHIVO_RSS = "logista.xml"

MESES = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}


def limpiar_texto(texto):
    return re.sub(
        r"\s+",
        " ",
        texto or "",
    ).strip()


def descargar_pagina(url):
    solicitud = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;"
                "q=0.9,*/*;q=0.8"
            ),
            "Accept-Language": "es-ES,es;q=0.9",
            "Cache-Control": "no-cache",
        },
    )

    with urllib.request.urlopen(
        solicitud,
        timeout=60,
    ) as respuesta:
        return respuesta.read()


def convertir_fecha(texto):
    texto = limpiar_texto(texto).lower()

    # Formato utilizado en el listado:
    # agosto 25, 2026
    coincidencia = re.search(
        r"\b("
        r"enero|febrero|marzo|abril|mayo|junio|"
        r"julio|agosto|septiembre|octubre|"
        r"noviembre|diciembre"
        r")\s+(\d{1,2}),\s+(\d{4})\b",
        texto,
        re.IGNORECASE,
    )

    if coincidencia:
        mes = MESES[coincidencia.group(1).lower()]
        dia = int(coincidencia.group(2))
        anio = int(coincidencia.group(3))

        try:
            return datetime(
                anio,
                mes,
                dia,
                8,
                0,
                tzinfo=timezone.utc,
            )

        except ValueError:
            return None

    # Formato que puede aparecer dentro del comunicado:
    # 25 de agosto de 2026
    coincidencia = re.search(
        r"\b(\d{1,2})\s+de\s+("
        r"enero|febrero|marzo|abril|mayo|junio|"
        r"julio|agosto|septiembre|octubre|"
        r"noviembre|diciembre"
        r")\s+de\s+(\d{4})\b",
        texto,
        re.IGNORECASE,
    )

    if coincidencia:
        dia = int(coincidencia.group(1))
        mes = MESES[coincidencia.group(2).lower()]
        anio = int(coincidencia.group(3))

        try:
            return datetime(
                anio,
                mes,
                dia,
                8,
                0,
                tzinfo=timezone.utc,
            )

        except ValueError:
            return None

    return None


def extraer_descripcion(soup):
    meta_og = soup.find(
        "meta",
        attrs={"property": "og:description"},
    )

    if meta_og and meta_og.get("content"):
        descripcion = limpiar_texto(
            meta_og["content"]
        )

        if len(descripcion) >= 50:
            return descripcion[:800]

    meta_normal = soup.find(
        "meta",
        attrs={"name": "description"},
    )

    if meta_normal and meta_normal.get("content"):
        descripcion = limpiar_texto(
            meta_normal["content"]
        )

        if len(descripcion) >= 50:
            return descripcion[:800]

    principal = (
        soup.find("main")
        or soup.find("article")
        or soup
    )

    for lista in principal.find_all("ul"):
        texto = limpiar_texto(
            lista.get_text(" ", strip=True)
        )

        if len(texto) >= 100:
            return texto[:800]

    for parrafo in principal.find_all("p"):
        texto = limpiar_texto(
            parrafo.get_text(" ", strip=True)
        )

        if len(texto) >= 100:
            return texto[:800]

    return "Nota de prensa oficial publicada por Logista."


def obtener_enlaces():
    contenido = descargar_pagina(
        PAGINA_PRINCIPAL
    )

    soup = BeautifulSoup(
        contenido,
        "html.parser",
    )

    enlaces = []
    enlaces_vistos = set()

    prefijo = (
        "/es/home/media/press-releases/"
    )

    for enlace in soup.find_all("a", href=True):
        href = limpiar_texto(
            enlace.get("href", "")
        )

        if not href:
            continue

        if href.lower().startswith("javascript:"):
            continue

        url = urljoin(
            BASE_URL,
            href,
        )

        url = url.split("#")[0].split("?")[0]

        if prefijo not in url:
            continue

        if not url.endswith(".html"):
            continue

        if url == PAGINA_PRINCIPAL:
            continue

        if url in enlaces_vistos:
            continue

        enlaces_vistos.add(url)
        enlaces.append(url)

    if not enlaces:
        raise RuntimeError(
            "No se encontraron notas de prensa de Logista"
        )

    return enlaces[:50]


def obtener_noticias():
    noticias = []

    for url in obtener_enlaces():
        try:
            contenido = descargar_pagina(url)

            soup = BeautifulSoup(
                contenido,
                "html.parser",
            )

            encabezado = soup.find("h1")

            if encabezado:
                titulo = limpiar_texto(
                    encabezado.get_text(
                        " ",
                        strip=True,
                    )
                )
            else:
                etiqueta_titulo = soup.find("title")

                if not etiqueta_titulo:
                    print(
                        f"No se encontró el título: {url}"
                    )
                    continue

                titulo = limpiar_texto(
                    etiqueta_titulo.get_text(
                        " ",
                        strip=True,
                    )
                )

            texto_pagina = limpiar_texto(
                soup.get_text(" ", strip=True)
            )

            fecha = convertir_fecha(texto_pagina)
            descripcion = extraer_descripcion(soup)

            noticias.append(
                {
                    "titulo": titulo,
                    "url": url,
                    "fecha": fecha,
                    "descripcion": descripcion,
                }
            )

            print(
                f"Noticia encontrada: {titulo}"
            )

        except Exception as error:
            print(
                f"No se pudo procesar {url}: {error}"
            )

    if not noticias:
        raise RuntimeError(
            "No se pudieron obtener las "
            "notas de prensa de Logista"
        )

    noticias.sort(
        key=lambda noticia: (
            noticia["fecha"]
            or datetime(
                1970,
                1,
                1,
                tzinfo=timezone.utc,
            )
        ),
        reverse=True,
    )

    return noticias[:40]


def crear_rss(noticias):
    rss = ET.Element(
        "rss",
        {
            "version": "2.0",
            "xmlns:atom": (
                "http://www.w3.org/2005/Atom"
            ),
        },
    )

    canal = ET.SubElement(
        rss,
        "channel",
    )

    ET.SubElement(
        canal,
        "title",
    ).text = "Logista – Notas de prensa"

    ET.SubElement(
        canal,
        "link",
    ).text = PAGINA_PRINCIPAL

    ET.SubElement(
        canal,
        "description",
    ).text = (
        "Últimas notas de prensa oficiales "
        "publicadas por Logista"
    )

    ET.SubElement(
        canal,
        "language",
    ).text = "es-es"

    ET.SubElement(
        canal,
        "ttl",
    ).text = "60"

    ET.SubElement(
        canal,
        "{http://www.w3.org/2005/Atom}link",
        {
            "href": (
                "https://raw.githubusercontent.com/"
                "plis2100/rss-logista/main/logista.xml"
            ),
            "rel": "self",
            "type": "application/rss+xml",
        },
    )

    ahora = datetime.now(timezone.utc)

    ET.SubElement(
        canal,
        "lastBuildDate",
    ).text = format_datetime(ahora)

    for noticia in noticias:
        elemento = ET.SubElement(
            canal,
            "item",
        )

        ET.SubElement(
            elemento,
            "title",
        ).text = noticia["titulo"]

        ET.SubElement(
            elemento,
            "link",
        ).text = noticia["url"]

        ET.SubElement(
            elemento,
            "guid",
            {"isPermaLink": "true"},
        ).text = noticia["url"]

        ET.SubElement(
            elemento,
            "description",
        ).text = noticia["descripcion"]

        ET.SubElement(
            elemento,
            "source",
            {"url": PAGINA_PRINCIPAL},
        ).text = "Logista"

        if noticia["fecha"]:
            ET.SubElement(
                elemento,
                "pubDate",
            ).text = format_datetime(
                noticia["fecha"]
            )

    arbol = ET.ElementTree(rss)

    ET.indent(
        arbol,
        space="  ",
    )

    arbol.write(
        ARCHIVO_RSS,
        encoding="utf-8",
        xml_declaration=True,
    )


def validar_rss():
    archivo = Path(ARCHIVO_RSS)

    if not archivo.exists():
        raise RuntimeError(
            "No se creó logista.xml"
        )

    if archivo.stat().st_size < 500:
        raise RuntimeError(
            "logista.xml está vacío"
        )

    raiz = ET.parse(archivo).getroot()

    elementos = raiz.findall(
        "./channel/item"
    )

    if not elementos:
        raise RuntimeError(
            "La RSS de Logista no contiene noticias"
        )

    return len(elementos)


def main():
    noticias = obtener_noticias()

    crear_rss(noticias)

    cantidad = validar_rss()

    print(
        f"RSS de Logista creada correctamente: "
        f"{cantidad} noticias"
    )

    print(
        f"Última noticia: "
        f"{noticias[0]['titulo']}"
    )

    print(
        f"Archivo generado: {ARCHIVO_RSS}"
    )


if __name__ == "__main__":
    main()

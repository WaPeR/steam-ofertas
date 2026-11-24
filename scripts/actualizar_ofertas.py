"""
Obtiene ofertas de Steam desde IsThereAnyDeal (ITAD).

- Consulta ofertas para España (EUR), Ucrania (UAH), Turquía (TRY) y Estados Unidos (USD).
- Conserva solo la tienda Steam.
- Genera un archivo JSON por región en data/.
- Requiere la variable de entorno ITAD_API_KEY.
"""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parent.parent
DATA = RAIZ / "data"

API_URL = "https://api.isthereanydeal.com/deals/v2"
STEAM_SHOP_ID = 61

REGIONES = [
    {"pais": "ES", "divisa": "EUR", "nombre": "España"},
    {"pais": "UA", "divisa": "UAH", "nombre": "Ucrania"},
    {"pais": "TR", "divisa": "TRY", "nombre": "Turquía"},
    {"pais": "US", "divisa": "USD", "nombre": "Estados Unidos"},
]

LIMITE_POR_PAGINA = 100
PAGINAS_POR_REGION = 3
PAUSA_ENTRE_PETICIONES = 2

CABECERAS = {
    "User-Agent": "OfertasSteamPersonal/1.0 (uso personal)",
    "ITAD-API-Key": os.environ.get("ITAD_API_KEY", ""),
}


def comprobar_api_key():
    if not CABECERAS["ITAD-API-Key"]:
        raise RuntimeError(
            "Falta ITAD_API_KEY. Créala en IsThereAnyDeal y expórtala antes de ejecutar el script."
        )


def obtener_pagina(pais, pagina):
    parametros = {
        "country": pais,
        "shops": STEAM_SHOP_ID,
        "sort": "-cut",
        "limit": LIMITE_POR_PAGINA,
        "offset": pagina * LIMITE_POR_PAGINA,
    }

    respuesta = requests.get(API_URL, headers=CABECERAS, params=parametros, timeout=30)

    if respuesta.status_code == 429:
        espera = int(respuesta.headers.get("Retry-After", "60"))
        print(f"Límite alcanzado. Esperando {espera} segundos...")
        time.sleep(espera)
        respuesta = requests.get(API_URL, headers=CABECERAS, params=parametros, timeout=30)

    respuesta.raise_for_status()
    return respuesta.json()


def extraer_appid(entrada):
    game = entrada.get("game") or {}
    appid = entrada.get("steamAppID") or game.get("appid") or entrada.get("appid")
    return str(appid) if appid else None


def normalizar_oferta(entrada):
    appid = extraer_appid(entrada)
    if not appid:
        return None

    tienda = entrada.get("shop") or {}
    if tienda.get("id") != STEAM_SHOP_ID and tienda.get("name", "").lower() != "steam":
        return None

    precio = entrada.get("price") or {}
    precio_regular = precio.get("regular") or {}
    divisa = precio.get("currency")

    precio_final = precio.get("amountInt")
    precio_original = precio_regular.get("amountInt")
    descuento = int(precio.get("cut") or 0)

    if not divisa or precio_final is None or descuento <= 0:
        return None

    game = entrada.get("game") or {}
    assets = game.get("assets") or {}

    return {
        "appid": appid,
        "nombre": game.get("title") or entrada.get("title") or "Juego desconocido",
        "url": entrada.get("url") or f"https://store.steampowered.com/app/{appid}/",
        "url_steam": f"https://store.steampowered.com/app/{appid}/",
        "imagen": assets.get("banner400") or assets.get("banner300") or assets.get("boxart"),
        "tienda": tienda.get("name") or "Steam",
        "divisa": divisa,
        "precio_final": precio_final / 100,
        "precio_original": (precio_original or 0) / 100,
        "descuento": descuento,
    }


def generar_region(region):
    pais = region["pais"]
    divisa = region["divisa"]
    ofertas = []
    ids_vistos = set()

    for pagina in range(PAGINAS_POR_REGION):
        print(f"[{pais}] Consultando página {pagina + 1} de {PAGINAS_POR_REGION}...")
        datos = obtener_pagina(pais, pagina)
        entradas = datos.get("list", datos if isinstance(datos, list) else [])

        for entrada in entradas:
            oferta = normalizar_oferta(entrada)
            if not oferta or oferta["appid"] in ids_vistos:
                continue
            ids_vistos.add(oferta["appid"])
            ofertas.append(oferta)

        if len(entradas) < LIMITE_POR_PAGINA:
            break
        time.sleep(PAUSA_ENTRE_PETICIONES)

    ofertas.sort(key=lambda oferta: (-oferta["descuento"], oferta["nombre"]))

    resultado = {
        "actualizado": datetime.now(timezone.utc).isoformat(),
        "fuente": "IsThereAnyDeal",
        "pais": pais,
        "nombre_region": region["nombre"],
        "divisa": divisa,
        "tienda": "Steam",
        "ofertas": ofertas,
    }

    archivo = DATA / f"ofertas-{pais.lower()}.json"
    archivo.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[{pais}] {len(ofertas)} ofertas guardadas en {archivo}")


def main():
    comprobar_api_key()
    DATA.mkdir(parents=True, exist_ok=True)
    for region in REGIONES:
        generar_region(region)


if __name__ == "__main__":
    main()

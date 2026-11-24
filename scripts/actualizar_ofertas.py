"""Consulta Steam en ITAD con diagnóstico seguro. Integración pendiente de validar."""
import json
import os
import re
import sys
import time
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import quote, quote_plus
import requests

DATA = Path(__file__).resolve().parent.parent / 'data'
API = 'https://api.isthereanydeal.com/deals/v2'
KEY = os.environ.get('ITAD_API_KEY', '').strip()
REGIONES = [('ES', 'España'), ('UA', 'Ucrania'), ('TR', 'Turquía'), ('US', 'Estados Unidos')]

def seguro(texto):
    texto = str(texto)
    if KEY:
        for variante in (KEY, quote(KEY, safe=''), quote_plus(KEY)):
            texto = texto.replace(variante, '[CLAVE OCULTA]')
    texto = re.sub(r'(?i)((?:key|token|secret|authorization)[\w-]*[\"\s:=]+)[^\s,<>]+', r'\1[OCULTO]', texto)
    return ''.join(c if c.isprintable() or c == '\n' else ' ' for c in texto)[:3000]

def consultar(pais, pagina):
    params = {'country': pais, 'shops': 61, 'sort': '-cut', 'limit': 100, 'offset': pagina * 100}
    print(f'ITAD: país={pais}, página={pagina + 1}; clave presente; autenticación por cabecera', flush=True)
    try:
        r = requests.get(API, params=params, headers={'ITAD-API-Key': KEY, 'User-Agent': 'OfertasSteamPersonal/1.0'}, timeout=30, allow_redirects=False)
    except requests.RequestException as exc:
        raise RuntimeError('Error de conexión: ' + seguro(exc)) from None
    print(f'HTTP {r.status_code}; tipo={seguro(r.headers.get("Content-Type", "desconocido"))}', flush=True)
    if not 200 <= r.status_code < 300:
        print('Mensaje del servidor (limitado y con clave oculta):', flush=True)
        print(seguro(r.text), flush=True)
        if r.status_code in (401, 403):
            print('Acceso rechazado: este estado por sí solo no distingue clave inválida, permisos o bloqueo. Revisar el mensaje anterior.', flush=True)
        if r.status_code == 429:
            print('Límite de consultas; Retry-After: ' + seguro(r.headers.get('Retry-After', 'no indicado')), flush=True)
        raise RuntimeError(f'Consulta interrumpida: HTTP {r.status_code}. No se publican datos nuevos.')
    try:
        datos = r.json()
    except ValueError:
        raise RuntimeError('La respuesta no es JSON. No se guardan datos.') from None
    print('Estructura raíz: ' + seguro(list(datos.keys()) if isinstance(datos, dict) else type(datos).__name__), flush=True)
    entradas = datos.get('list') if isinstance(datos, dict) else datos
    if not isinstance(entradas, list):
        raise RuntimeError('Estructura inesperada: falta una lista de ofertas. No se guardan datos.')
    if entradas:
        primera = entradas[0]
        print('Claves de primera oferta: ' + seguro(list(primera) if isinstance(primera, dict) else type(primera).__name__), flush=True)
        if isinstance(primera, dict):
            for campo in ('deal', 'price', 'game', 'shop'):
                if isinstance(primera.get(campo), dict):
                    print(f'Claves de {campo}: ' + seguro(list(primera[campo])), flush=True)
    return entradas

def normalizar(e):
    game = e.get('game') or {}
    appid = e.get('steamAppID') or game.get('appid') or e.get('appid')
    shop = e.get('shop') or {}
    p = e.get('price') or {}
    regular = p.get('regular') or {}
    if not appid or shop.get('id') != 61 or not p.get('currency') or p.get('amountInt') is None or not p.get('cut'):
        return None
    return {'appid': str(appid), 'nombre': game.get('title') or e.get('title') or 'Juego desconocido', 'url_steam': f'https://store.steampowered.com/app/{appid}/', 'imagen': (game.get('assets') or {}).get('banner400'), 'tienda': 'Steam', 'divisa': p['currency'], 'precio_final': p['amountInt'] / 100, 'precio_original': regular.get('amountInt', 0) / 100, 'descuento': int(p['cut'])}

def main():
    if not KEY:
        raise RuntimeError('ITAD_API_KEY falta o está vacío. Revisar el secreto de Actions.')
    pendientes = {}
    for pais, nombre in REGIONES:
        ofertas = {}
        for pagina in range(3):
            entradas = consultar(pais, pagina)
            validas = [o for e in entradas if isinstance(e, dict) and (o := normalizar(e))]
            print(f'{pais}: recibidas={len(entradas)}, reconocidas={len(validas)}', flush=True)
            if entradas and not validas:
                raise RuntimeError('El parser no reconoce las ofertas. Usar las claves registradas para corregirlo; no se sobrescriben los JSON.')
            for o in validas:
                ofertas[o['appid']] = o
            time.sleep(2)
            if len(entradas) < 100:
                break
        monedas = {o['divisa'] for o in ofertas.values()}
        if len(monedas) != 1:
            raise RuntimeError('Respuesta vacía o con varias divisas; no se sobrescriben los JSON.')
        pendientes[pais] = {'actualizado': datetime.now(timezone.utc).isoformat(), 'fuente': 'IsThereAnyDeal', 'pais': pais, 'nombre_region': nombre, 'divisa': monedas.pop(), 'tienda': 'Steam', 'ofertas': list(ofertas.values())}
    DATA.mkdir(parents=True, exist_ok=True)
    for pais, datos in pendientes.items():
        (DATA / f'ofertas-{pais.lower()}.json').write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding='utf-8')

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('ERROR: ' + seguro(exc), flush=True)
        sys.exit(1)

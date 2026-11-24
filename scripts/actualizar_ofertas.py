"""Obtiene ofertas Steam de ITAD sin convertir divisas."""
import json
import os
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import quote, quote_plus, urlparse
import requests

DATA = Path(__file__).resolve().parent.parent / 'data'
API_URL = 'https://api.isthereanydeal.com/deals/v2'
STEAM_SHOP_ID = 61
REGIONES = [('ES', 'España'), ('UA', 'Ucrania'), ('TR', 'Turquía'), ('US', 'Estados Unidos')]
LIMITE = 100
MAX_PAGINAS = 3
PAUSA = 2
API_KEY = os.environ.get('ITAD_API_KEY', '').strip()

def ocultar_secreto(texto):
    texto = str(texto)
    if API_KEY:
        for variante in (API_KEY, quote(API_KEY, safe=''), quote_plus(API_KEY)):
            texto = texto.replace(variante, '[CLAVE OCULTA]')
    return ''.join(c if c.isprintable() or c == '\n' else ' ' for c in texto)[:2000]

def importe(objeto):
    if not isinstance(objeto, dict) or objeto.get('amount') is None:
        raise ValueError('Falta amount en un precio.')
    try:
        numero = Decimal(str(objeto['amount']))
    except InvalidOperation:
        raise ValueError('Importe no numérico.') from None
    if not numero.is_finite() or numero < 0:
        raise ValueError('Importe inválido.')
    return float(numero)

def url_https(valor):
    if not isinstance(valor, str):
        return None
    partes = urlparse(valor)
    return valor if partes.scheme == 'https' and partes.netloc else None

def consultar(session, pais, offset):
    params = {'country': pais, 'shops': STEAM_SHOP_ID, 'sort': '-cut', 'limit': LIMITE, 'offset': offset}
    print(f'[{pais}] Consultando offset={offset}', flush=True)
    try:
        respuesta = session.get(API_URL, params=params, timeout=30, allow_redirects=False)
    except requests.RequestException:
        raise RuntimeError(f'[{pais}] Error de conexión con ITAD.') from None
    print(f'[{pais}] HTTP {respuesta.status_code}', flush=True)
    if respuesta.status_code != 200:
        mensaje = 'Sin mensaje JSON reconocido.'
        try:
            error = respuesta.json()
            if isinstance(error, dict):
                mensaje = error.get('reason_phrase') or mensaje
        except ValueError:
            mensaje = 'El servidor no devolvió JSON.'
        raise RuntimeError(f'[{pais}] HTTP {respuesta.status_code}: {ocultar_secreto(mensaje)}')
    try:
        datos = respuesta.json()
    except ValueError:
        raise RuntimeError(f'[{pais}] JSON inválido.') from None
    if not isinstance(datos, dict) or not isinstance(datos.get('list'), list):
        raise RuntimeError(f'[{pais}] Estructura de respuesta inesperada.')
    return datos

def normalizar(entrada):
    if not isinstance(entrada, dict) or not isinstance(entrada.get('deal'), dict):
        raise ValueError('Falta el objeto deal.')
    deal = entrada['deal']
    tienda = deal.get('shop') or {}
    if str(tienda.get('id')) != str(STEAM_SHOP_ID):
        return None
    identificador = entrada.get('id')
    titulo = entrada.get('title')
    enlace = url_https(deal.get('url'))
    if not identificador or not titulo or not enlace:
        raise ValueError('Falta id, title o enlace HTTPS.')
    precio = deal.get('price') or {}
    regular = deal.get('regular') or {}
    divisa = precio.get('currency')
    if not isinstance(divisa, str) or not divisa or regular.get('currency') != divisa:
        raise ValueError('Divisas ausentes o distintas.')
    precio_final = importe(precio)
    precio_original = importe(regular)
    try:
        descuento = float(deal['cut'])
    except (KeyError, TypeError, ValueError):
        raise ValueError('Descuento inválido.') from None
    if not 0 <= descuento <= 100:
        raise ValueError('Descuento fuera de rango.')
    if descuento <= 0:
        return None
    assets = entrada.get('assets') or {}
    imagen = next((u for campo in ('banner400', 'banner300', 'boxart') if (u := url_https(assets.get(campo)))), None)
    return {
        'id': str(identificador), 'nombre': titulo, 'url': enlace,
        'url_steam': enlace, 'imagen': imagen, 'tienda': 'Steam',
        'divisa': divisa, 'precio_final': precio_final,
        'precio_original': precio_original, 'descuento': descuento,
        'caduca': deal.get('expiry'),
    }

def generar_region(session, pais, nombre):
    ofertas = {}
    offset = 0
    offsets_vistos = set()
    hay_mas = False
    for pagina in range(MAX_PAGINAS):
        if offset in offsets_vistos:
            raise RuntimeError(f'[{pais}] Offset repetido.')
        offsets_vistos.add(offset)
        datos = consultar(session, pais, offset)
        entradas = datos['list']
        reconocidas = 0
        for entrada in entradas:
            try:
                oferta = normalizar(entrada)
            except (ValueError, TypeError, AttributeError) as error:
                raise RuntimeError(f'[{pais}] Error al interpretar una oferta: {error}. No se guardarán datos nuevos.') from None
            if oferta is not None:
                ofertas[oferta['id']] = oferta
                reconocidas += 1
        print(f'[{pais}] Página {pagina + 1}: recibidas={len(entradas)}, reconocidas={reconocidas}', flush=True)
        hay_mas = datos.get('hasMore') is True
        if not hay_mas:
            break
        siguiente = datos.get('nextOffset')
        if not isinstance(siguiente, int) or isinstance(siguiente, bool) or siguiente <= offset:
            raise RuntimeError(f'[{pais}] nextOffset inválido.')
        offset = siguiente
        time.sleep(PAUSA)
    if not ofertas:
        raise RuntimeError(f'[{pais}] Sin ofertas reconocidas; se conservan los archivos anteriores.')
    divisas = {o['divisa'] for o in ofertas.values()}
    if len(divisas) != 1:
        raise RuntimeError(f'[{pais}] Varias divisas: {sorted(divisas)}.')
    divisa = next(iter(divisas))
    print(f'[{pais}] {len(ofertas)} ofertas; divisa recibida: {divisa}', flush=True)
    return {
        'actualizado': datetime.now(timezone.utc).isoformat(),
        'fuente': 'IsThereAnyDeal', 'pais': pais, 'nombre_region': nombre,
        'divisa': divisa, 'tienda': 'Steam', 'hay_mas': hay_mas,
        'ofertas': sorted(ofertas.values(), key=lambda o: (-o['descuento'], o['nombre'].casefold())),
    }

def main():
    if not API_KEY:
        raise RuntimeError('Falta ITAD_API_KEY o está vacío.')
    pendientes = {}
    with requests.Session() as session:
        session.headers.update({'ITAD-API-Key': API_KEY, 'User-Agent': 'OfertasSteamPersonal/1.0', 'Accept': 'application/json'})
        for pais, nombre in REGIONES:
            pendientes[pais] = generar_region(session, pais, nombre)
            time.sleep(PAUSA)
    DATA.mkdir(parents=True, exist_ok=True)
    for pais, datos in pendientes.items():
        archivo = DATA / f'ofertas-{pais.lower()}.json'
        temporal = archivo.with_suffix('.json.tmp')
        temporal.write_text(json.dumps(datos, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
        temporal.replace(archivo)
        print(f'Guardado {archivo.name}: {len(datos["ofertas"])} ofertas.', flush=True)

if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('ERROR: ' + ocultar_secreto(error), flush=True)
        sys.exit(1)

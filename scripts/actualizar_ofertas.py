"""Descarga ofertas Steam de España y Ucrania sin conversiones."""
import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import quote, quote_plus, urlparse
from decimal import Decimal
import requests

DATA = Path(__file__).resolve().parent.parent / 'data'
KEY = os.environ.get('ITAD_API_KEY', '').strip()
REGIONES = [('ES', 'España', 'EUR'), ('UA', 'Ucrania', 'UAH')]
MAX_PAGINAS = 1000
PAUSA = 7

def seguro(texto):
    texto = str(texto)
    if KEY:
        for valor in (KEY, quote(KEY, safe=''), quote_plus(KEY)):
            texto = texto.replace(valor, '[OCULTO]')
    return ''.join(c if c.isprintable() else ' ' for c in texto)[:500]

def https(valor):
    if not isinstance(valor, str):
        return None
    p = urlparse(valor)
    return valor if p.scheme == 'https' and p.netloc else None

def importe(p):
    n = Decimal(str(p['amount']))
    if not n.is_finite() or n < 0:
        raise ValueError('Importe inválido')
    return float(n)

def normalizar(e, divisa):
    d = e['deal']
    if str(d['shop']['id']) != '61':
        return None
    p, r = d['price'], d['regular']
    if p.get('currency') != divisa or r.get('currency') != divisa:
        raise ValueError('La divisa recibida no coincide con ' + divisa)
    cut = float(d['cut'])
    if not 0 <= cut <= 100:
        raise ValueError('Descuento inválido')
    if cut == 0:
        return None
    url = https(d.get('url'))
    if not url or not e.get('id') or not e.get('title'):
        raise ValueError('Oferta sin identificador, título o enlace HTTPS')
    assets = e.get('assets') or {}
    imagen = next((u for k in ('banner400', 'banner300', 'boxart') if (u := https(assets.get(k)))), None)
    return {'id': str(e['id']), 'nombre': e['title'], 'tipo': e.get('type'), 'url': url, 'url_steam': url, 'imagen': imagen, 'tienda': 'Steam', 'divisa': divisa, 'precio_final': importe(p), 'precio_original': importe(r), 'descuento': cut, 'caduca': d.get('expiry')}

def consultar(session, pais, offset):
    params = {'country': pais, 'shops': 61, 'sort': '-cut', 'limit': 100, 'offset': offset}
    for intento in range(3):
        time.sleep(PAUSA)
        try:
            r = session.get('https://api.isthereanydeal.com/deals/v2', params=params, timeout=45, allow_redirects=False)
        except requests.RequestException:
            if intento < 2:
                continue
            raise RuntimeError('Error de conexión; se conservan los datos anteriores') from None
        if r.status_code == 429 or 500 <= r.status_code < 600:
            if intento < 2:
                espera = r.headers.get('Retry-After', '')
                time.sleep(min(300, max(60, int(espera))) if espera.isdigit() else 60)
                continue
        if r.status_code != 200:
            mensaje = ''
            try:
                body = r.json()
                mensaje = body.get('reason_phrase', '') if isinstance(body, dict) else ''
            except ValueError:
                pass
            raise RuntimeError(f'{pais}: HTTP {r.status_code}: {seguro(mensaje)}')
        datos = r.json()
        if not isinstance(datos, dict) or not isinstance(datos.get('list'), list) or not isinstance(datos.get('hasMore'), bool):
            raise ValueError('Respuesta ITAD inesperada')
        return datos

def region(session, pais, nombre, divisa):
    ofertas, vistos = {}, set()
    offset = 0
    mas = False
    for pagina in range(MAX_PAGINAS):
        if offset in vistos:
            raise ValueError('Paginación repetida')
        vistos.add(offset)
        datos = consultar(session, pais, offset)
        for e in datos['list']:
            o = normalizar(e, divisa)
            if o:
                ofertas[o['id']] = o
        print(f'{pais}: página {pagina + 1}, {len(ofertas)} ofertas', flush=True)
        mas = datos['hasMore']
        if not mas:
            break
        siguiente = datos.get('nextOffset')
        if type(siguiente) is not int or siguiente <= offset:
            raise ValueError('nextOffset inválido')
        offset = siguiente
    if not ofertas:
        raise ValueError(pais + ': sin ofertas reconocidas; se conservan los datos anteriores')
    if mas:
        print(pais + ': límite de seguridad alcanzado; listado marcado como incompleto', flush=True)
    return {'actualizado': datetime.now(timezone.utc).isoformat(), 'fuente': 'IsThereAnyDeal', 'pais': pais, 'nombre_region': nombre, 'divisa': divisa, 'tienda': 'Steam', 'hay_mas': mas, 'ofertas': sorted(ofertas.values(), key=lambda o: (-o['descuento'], o['nombre'].casefold()))}

def main():
    if not KEY:
        raise ValueError('Falta ITAD_API_KEY')
    with requests.Session() as s:
        s.headers.update({'ITAD-API-Key': KEY, 'User-Agent': 'OfertasSteamPersonal/1.0', 'Accept': 'application/json'})
        pendientes = {pais: region(s, pais, nombre, divisa) for pais, nombre, divisa in REGIONES}
    DATA.mkdir(parents=True, exist_ok=True)
    for pais, datos in pendientes.items():
        destino = DATA / f'ofertas-{pais.lower()}.json'
        temporal = destino.with_suffix('.json.tmp')
        temporal.write_text(json.dumps(datos, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
        temporal.replace(destino)

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print('ERROR: ' + seguro(e), flush=True)
        sys.exit(1)

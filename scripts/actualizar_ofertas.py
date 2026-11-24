"""Ofertas nativas de Steam Ucrania. No usa ITAD ni convierte precios."""
import json
import re
import sys
import time
from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal
import requests
from bs4 import BeautifulSoup

DATA = Path(__file__).resolve().parent.parent / 'data'
REGIONES = [('ua', 'Ucrania', 'UAH')]

def dinero(texto):
    if '₴' not in texto:
        raise ValueError('Precio sin símbolo UAH: ' + texto)
    limpio = re.sub(r'[\s\u00a0\u202f₴]', '', texto).replace(',', '.')
    if not re.fullmatch(r'\d+(?:\.\d{1,2})?', limpio):
        raise ValueError('Formato monetario no reconocido: ' + texto)
    return Decimal(limpio)

def obtener(s, pais, inicio):
    params = {'cc': pais, 'l': 'english', 'specials': 1, 'category1': 998, 'start': inicio, 'count': 100, 'infinite': 1, 'filter': 'all'}
    for intento in range(3):
        time.sleep(7)
        try:
            r = s.get('https://store.steampowered.com/search/results/', params=params, timeout=45)
            if r.status_code == 429 or r.status_code >= 500:
                if intento < 2:
                    time.sleep(60)
                    continue
            r.raise_for_status()
            d = r.json()
            if not isinstance(d, dict) or not isinstance(d.get('results_html'), str):
                raise ValueError('Steam no devuelve resultados HTML en JSON')
            total = int(d['total_count'])
            if total < 0:
                raise ValueError('Total inválido')
            return d['results_html'], total
        except requests.RequestException:
            if intento == 2:
                raise RuntimeError('Error HTTP o de conexión con Steam; se conservan los datos anteriores') from None
    raise RuntimeError('No se pudo consultar Steam')

def generar(s, pais, nombre, moneda):
    inicio, ofertas, paginas = 0, {}, set()
    while True:
        html, total = obtener(s, pais, inicio)
        filas = BeautifulSoup(html, 'html.parser').select('a.search_result_row')
        if not filas:
            if inicio < total:
                raise ValueError('Página vacía antes del final; no se publicará un listado parcial')
            break
        firma = tuple(f.get('href', '') for f in filas)
        if firma in paginas:
            raise ValueError('Steam repite una página; se conservan los datos anteriores')
        paginas.add(firma)
        for f in filas:
            ids = f.get('data-ds-appid', '')
            if not re.fullmatch(r'\d+', ids) or '/app/' not in f.get('href', ''):
                continue
            pct = f.select_one('.discount_pct')
            if pct is None:
                continue
            coincidencia = re.fullmatch(r'-?(\d+)%', pct.get_text(strip=True))
            if not coincidencia:
                raise ValueError('Formato de descuento inesperado')
            descuento = int(coincidencia.group(1))
            if descuento < 50:
                continue
            if descuento > 100:
                raise ValueError('Descuento inválido')
            final = f.select_one('.discount_final_price')
            original = f.select_one('.discount_original_price')
            titulo = f.select_one('.title')
            if final is None or original is None or titulo is None:
                raise ValueError('Faltan título o precios; posible cambio de formato de Steam')
            p, anterior = dinero(final.get_text()), dinero(original.get_text())
            if anterior <= 0 or p > anterior:
                raise ValueError('Importes incoherentes')
            if abs((anterior - p) / anterior * 100 - descuento) > 2:
                raise ValueError('Precio y descuento no coinciden')
            ofertas[ids] = {'id': ids, 'nombre': titulo.get_text(strip=True), 'tipo': 'game', 'url': f'https://store.steampowered.com/app/{ids}/?cc={pais}', 'url_steam': f'https://store.steampowered.com/app/{ids}/?cc={pais}', 'imagen': f'https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/{ids}/header.jpg', 'tienda': 'Steam', 'divisa': moneda, 'precio_final': float(p), 'precio_original': float(anterior), 'descuento': descuento}
        inicio += len(filas)
        print(f'{pais}: {inicio}/{total} resultados examinados; {len(ofertas)} ofertas >=50%', flush=True)
        if inicio >= total:
            break
        if len(paginas) >= 1000:
            raise ValueError('Límite de seguridad; no se publicará un listado parcial')
    if not ofertas:
        raise ValueError('No hay ofertas válidas; se conservan los datos anteriores')
    return {'actualizado': datetime.now(timezone.utc).isoformat(), 'fuente': 'Steam Store', 'pais': pais.upper(), 'nombre_region': nombre, 'divisa': moneda, 'tienda': 'Steam', 'hay_mas': False, 'descuento_minimo': 50, 'ofertas': sorted(ofertas.values(), key=lambda o: (-o['descuento'], o['nombre'].casefold()))}

def main():
    DATA.mkdir(parents=True, exist_ok=True)
    errores = []
    with requests.Session() as s:
        s.headers.update({'User-Agent': 'SteamOfertasPersonal/2.0', 'Accept-Language': 'en-US,en;q=0.9'})
        for pais, nombre, moneda in REGIONES:
            try:
                datos = generar(s, pais, nombre, moneda)
                destino = DATA / f'ofertas-{pais}.json'
                temporal = destino.with_suffix('.json.tmp')
                temporal.write_text(json.dumps(datos, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
                temporal.replace(destino)
                print(f'Guardado {pais}: {len(datos["ofertas"])} ofertas', flush=True)
            except Exception as e:
                errores.append(pais)
                print(f'ERROR {pais}: {e}', flush=True)
    return 1 if errores else 0

if __name__ == '__main__':
    sys.exit(main())

"""Prueba precios nativos UAH en Steam sin modificar los datos de la web.
Uso: python probar_steam_uah.py
     python probar_steam_uah.py 1693980 1930150
Solo biblioteca estándar. Guarda un informe JSON y termina con código 1
si alguna consulta falla o no devuelve un precio en UAH.
"""
import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def consultar(appid):
    url = 'https://store.steampowered.com/api/appdetails?' + urlencode({
        'appids': appid, 'cc': 'ua', 'l': 'spanish'
    })
    resultado = {'appid': appid, 'url': url, 'valido_uah': False}
    try:
        solicitud = Request(url, headers={
            'User-Agent': 'SteamUAHDiagnostic/1.0', 'Accept': 'application/json'
        })
        with urlopen(solicitud, timeout=30) as respuesta:
            datos = json.load(respuesta)
        item = datos.get(str(appid), {})
        if item.get('success') is not True:
            raise ValueError('Steam no devuelve success=true para este juego y región')
        detalle = item.get('data') or {}
        resultado.update(nombre=detalle.get('name'), tipo=detalle.get('type'))
        precio = detalle.get('price_overview')
        if not isinstance(precio, dict):
            raise ValueError('Sin price_overview: puede no tener precio individual o no estar disponible')
        resultado['price_overview'] = precio
        if precio.get('currency') != 'UAH':
            raise ValueError('Moneda recibida: ' + str(precio.get('currency')) + '; se esperaba UAH')
        for campo in ('initial', 'final', 'discount_percent'):
            if type(precio.get(campo)) is not int:
                raise ValueError('Campo de precio inválido: ' + campo)
        if precio['initial'] < 0 or precio['final'] < 0 or not 0 <= precio['discount_percent'] <= 100:
            raise ValueError('Importes o descuento fuera de rango')
        resultado.update(
            valido_uah=True,
            precio_original_uah=precio['initial'] / 100,
            precio_final_uah=precio['final'] / 100,
            descuento=precio['discount_percent'],
            cumple_descuento=precio['discount_percent'] >= 50,
            es_juego=detalle.get('type') == 'game',
            incluir_como_juego=detalle.get('type') == 'game' and precio['discount_percent'] >= 50
        )
    except HTTPError as error:
        resultado['error'] = f'HTTP {error.code}; no se reintenta automáticamente'
    except (URLError, TimeoutError, ValueError, TypeError, AttributeError, OSError) as error:
        resultado['error'] = str(error)
    return resultado


def appid_valido(texto):
    if not texto.isascii() or not texto.isdigit() or int(texto) <= 0:
        raise argparse.ArgumentTypeError('El AppID debe ser un entero positivo')
    return int(texto)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('appids', nargs='*', type=appid_valido,
                        help='IDs de Steam; sin argumentos prueba tres juegos conocidos')
    parser.add_argument('--salida', default='prueba-steam-uah.json')
    args = parser.parse_args()
    ids = list(dict.fromkeys(args.appids or [1693980, 220, 620]))
    if len(ids) > 10:
        parser.error('Esta prueba está limitada a 10 juegos')
    resultados = []
    for indice, appid in enumerate(ids):
        if indice:
            time.sleep(7)
        item = consultar(appid)
        resultados.append(item)
        nombre = item.get('nombre') or str(appid)
        if item['valido_uah']:
            etiqueta = 'cumple >=50%' if item['cumple_descuento'] else 'no cumple >=50%'
            print(f"OK {nombre}: {item['precio_final_uah']:.2f} UAH; "
                  f"-{item['descuento']}%; tipo={item.get('tipo')}; {etiqueta}", flush=True)
        else:
            print(f"ERROR {nombre}: {item.get('error')}", flush=True)
    informe = {
        'consultado_utc': datetime.now(timezone.utc).isoformat(),
        'pais_solicitado': 'UA', 'divisa_esperada': 'UAH',
        'total': len(resultados),
        'precios_uah_validos': sum(r['valido_uah'] for r in resultados),
        'juegos_con_descuento_minimo': sum(r.get('incluir_como_juego', False) for r in resultados),
        'resultados': resultados
    }
    destino = Path(args.salida)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(informe, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    print(f"Informe: {destino}; precios UAH válidos: "
          f"{informe['precios_uah_validos']}/{informe['total']}", flush=True)
    return 0 if informe['precios_uah_validos'] == informe['total'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

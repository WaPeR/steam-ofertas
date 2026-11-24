# Ofertas diarias de Steam

Web personal para consultar ofertas de la tienda oficial de Steam por región.

## Regiones y divisas

- España: EUR
- Ucrania: UAH
- Turquía: TRY
- Estados Unidos: USD

Los precios no se convierten desde dólares: el script consulta IsThereAnyDeal para cada país y guarda el precio en la divisa correspondiente a esa región.

## Fuente de datos

El proyecto usa la API de [IsThereAnyDeal](https://isthereanydeal.com/).

- Filtra las ofertas para conservar únicamente la tienda Steam.
- Consulta España, Ucrania, Turquía y Estados Unidos.
- Genera un archivo JSON por región.
- Usa la API key mediante la variable de entorno `ITAD_API_KEY`.

## Configurar la API key

1. Crea una cuenta en IsThereAnyDeal.
2. Registra una aplicación y genera una API key.
3. En GitHub, abre **Settings > Secrets and variables > Actions**.
4. Crea un secreto llamado `ITAD_API_KEY` y pega ahí tu clave.

Para probarlo localmente:

```bash
export ITAD_API_KEY="tu_api_key"
python scripts/actualizar_ofertas.py
python -m http.server 8000
```

En Windows PowerShell:

```powershell
$env:ITAD_API_KEY = "tu_api_key"
python scripts/actualizar_ofertas.py
python -m http.server 8000
```

## Ejecutar la web

```bash
python -m http.server 8000
```

Abre `http://localhost:8000`.

## Actualización automática

El workflow de GitHub Actions se ejecuta cada día a las 07:00 UTC, consulta las cuatro regiones y publica la web en GitHub Pages.

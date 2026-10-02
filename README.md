# Scanner

Herramienta de descubrimiento de superficie de ataque. Le das un dominio y encadena estos pasos:

1. `subfinder` saca los subdominios del dominio.
2. `httpx` comprueba cuáles responden y descarta los que redirigen a un host que ya estaba en la lista.
3. Dorking con DuckDuckGo (`site:host`) sobre cada host vivo para sacar rutas indexadas.
4. `waybackurls` saca endpoints históricos de los hosts vivos. Solo se ejecuta si pasas la flag `--wayback`.
5. `httpx` valida todos los endpoints recogidos y deja solo los que siguen activos.

El progreso se guarda por dominio, así que si cancelas con Ctrl+C y vuelves a lanzarlo sobre el mismo dominio continúa donde lo dejó.

## Requisitos

Herramientas externas en el PATH (o en `~/go/bin`): `subfinder`, `httpx` y `waybackurls`.

Dependencia de Python (para el dorking):

```
pip install -r requirements.txt
```

Python 3.8 o superior.

## Uso

```
python3 scanner.py dominio.com
```

Con waybackurls incluido:

```
python3 scanner.py dominio.com --wayback
```

Los resultados se guardan en `output/dominio.com/` junto al propio script.

## Flags

| Flag | Descripción | Default |
|------|-------------|---------|
| `-o`, `--output` | Carpeta base de salida | `output/` junto al script |
| `-t`, `--threads` | Hilos para httpx | `50` |
| `--timeout` | Timeout por petición de httpx en segundos | `7` |
| `--exclude-codes` | Códigos HTTP a descartar en el httpx final | `404,410` |
| `--keep-static` | No descartar imágenes, css, fuentes y vídeo | off |
| `--max-subs` | Limita el número de subdominios a procesar (0 = sin límite) | `0` |
| `--sf-maxtime` | Minutos máximos para subfinder | `5` |
| `--sf-timeout` | Segundos de espera por fuente en subfinder | `10` |
| `--no-all` | No usar la opción `-all` de subfinder (más rápido, menos fuentes) | off |
| `--wayback` | Ejecutar también waybackurls | off |
| `--dork-max` | Máximo de resultados por host en el dorking | `50` |
| `--dork-pause` | Segundos de espera entre consultas a DuckDuckGo | `2.0` |
| `--dork-region` | Región de búsqueda de DuckDuckGo | `wt-wt` |
| `--dork-max-fails` | Fallos seguidos tras los que se aborta el dorking (rate limit) | `5` |
| `--fresh` | Ignora el progreso previo y empieza de cero | off |

## Salida

| Fichero | Contenido |
|---------|-----------|
| `1_subdomains.txt` | Subdominios encontrados |
| `2_alive_hosts.txt` | Hosts que responden |
| `2_skipped_redirects.txt` | Hosts descartados por redirect y el motivo |
| `3_dork_urls.txt` | Endpoints encontrados por dorking |
| `4_wayback_urls.txt` | Endpoints históricos (solo con `--wayback`) |
| `5_live_endpoints.txt` | Endpoints que siguen activos |
| `5_live_endpoints_status.tsv` | Los mismos endpoints con código y tamaño |

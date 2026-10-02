# Scanner

Herramienta de descubrimiento de superficie de ataque. Le das un dominio y encadena cuatro pasos:

1. `subfinder` saca los subdominios del dominio.
2. `httpx` comprueba cuáles responden y descarta los que redirigen a un host que ya estaba en la lista.
3. `waybackurls` saca endpoints históricos de los hosts vivos.
4. `httpx` vuelve a comprobar esos endpoints y deja solo los que siguen activos.

El progreso se guarda por dominio, así que si cancelas con Ctrl+C y vuelves a lanzarlo sobre el mismo dominio continúa donde lo dejó.

## Requisitos

`subfinder`, `httpx` y `waybackurls` instalados y accesibles en el PATH (o en `~/go/bin`). Python 3.8 o superior.

## Uso

```
python3 scanner.py dominio.com
```

Los resultados se guardan en `output/dominio.com/` junto al propio script.

## Flags

| Flag | Descripción | Default |
|------|-------------|---------|
| `-o`, `--output` | Carpeta base de salida | `output/` junto al script |
| `-t`, `--threads` | Hilos para httpx | `50` |
| `--timeout` | Timeout por petición de httpx en segundos | `7` |
| `--exclude-codes` | Códigos HTTP a descartar en el httpx final | `404,410` |
| `--keep-static` | No descartar imágenes, css, fuentes y vídeo de waybackurls | off |
| `--max-subs` | Limita el número de subdominios a procesar (0 = sin límite) | `0` |
| `--sf-maxtime` | Minutos máximos para subfinder | `5` |
| `--sf-timeout` | Segundos de espera por fuente en subfinder | `10` |
| `--no-all` | No usar la opción `-all` de subfinder (más rápido, menos fuentes) | off |
| `--fresh` | Ignora el progreso previo y empieza de cero | off |

## Salida

| Fichero | Contenido |
|---------|-----------|
| `1_subdomains.txt` | Subdominios encontrados |
| `2_alive_hosts.txt` | Hosts que responden |
| `2_skipped_redirects.txt` | Hosts descartados por redirect y el motivo |
| `3_wayback_urls.txt` | Endpoints históricos únicos |
| `4_alive_urls.txt` | Endpoints que siguen activos |
| `4_alive_urls_status.tsv` | Los mismos endpoints con código y tamaño |

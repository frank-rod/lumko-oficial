# Generar y descargar imagenes

Este proyecto genera los assets de `assets/ai/` con el script:

```bash
python3 tools/generate_images.py
```

El script usa primero DefAPI con `openai/gpt-image-2` si encuentra una llave de DefAPI en `.env`. Si no hay llave de DefAPI, usa OpenAI directo con fallback entre `gpt-image-2`, `gpt-image-1.5` y `gpt-image-1`.

## 1. Configurar `.env`

En la raiz del proyecto debe existir `.env`.

Para usar DefAPI:

```bash
DEFAPI=dk-tu-api-key
```

Tambien acepta estos nombres:

```bash
DEFAPI_API_KEY=dk-tu-api-key
DEFAPI_KEY=dk-tu-api-key
```

Para usar OpenAI directo como fallback:

```bash
OPENAI_API_KEY=sk-tu-api-key
```

No subas `.env` a repositorios ni pegues las llaves en chats.

## 2. Generar todas las imagenes

Ejecuta:

```bash
python3 tools/generate_images.py
```

El script genera y reemplaza estos archivos:

```text
assets/ai/hero-bg.png
assets/ai/studio-vibe.png
assets/ai/process-bg.png
assets/ai/cta-bg.png
```

Con DefAPI, el flujo es asincrono:

1. Crea una tarea en `https://api.defapi.org/api/gpt-image/gen`.
2. Recibe un `task_id`.
3. Consulta el estado en `/api/task/query`.
4. Cuando el estado es `success`, descarga la URL de la imagen.
5. Guarda el PNG en `assets/ai/`.

Durante la ejecucion veras mensajes como:

```text
[hero-bg.png] requesting DefAPI openai/gpt-image-2 1536x1024 ...
  DefAPI task ta...: created
  DefAPI task ta...: pending
  DefAPI task ta...: downloading result
[hero-bg.png] saved (1910 KB) via DefAPI openai/gpt-image-2
```

## 3. Agregar o cambiar imagenes

Edita `tools/generate_images.py` y modifica la lista `JOBS`.

Ejemplo:

```python
{
    "name": "new-section-bg.png",
    "size": "1536x1024",
    "prompt": (
        "Premium abstract background for a digital studio website. "
        "Warm cream base, deep teal shapes, mint accents, no text, no logos."
    ),
},
```

Campos:

- `name`: nombre final dentro de `assets/ai/`.
- `size`: resolucion o proporcion aceptada por el proveedor.
- `prompt`: descripcion clara de la imagen.

DefAPI soporta valores como:

```text
auto
1:1
3:2
2:3
16:9
9:16
1024x1024
1536x1024
1024x1536
2048x2048
3840x2160
2160x3840
```

Para resoluciones custom, usa multiplos de 16, maximo 3840 px por lado, ratio maximo 3:1 y entre 655360 y 8294400 pixeles totales.

## 4. Descargar resultados ya generados

Si DefAPI ya creo una tarea pero el script fallo al descargar, puedes consultar el `task_id` desde los logs.

La consulta manual es:

```bash
curl -H "Authorization: Bearer $DEFAPI" \
  "https://api.defapi.org/api/task/query?task_id=TU_TASK_ID"
```

La respuesta exitosa trae:

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "status": "success",
    "result": [
      {
        "image": "https://..."
      }
    ]
  }
}
```

Descarga esa URL con un `User-Agent` de navegador. Algunas URLs de DefAPI pueden devolver `403 error code: 1010` si se descargan sin headers.

Ejemplo:

```bash
curl -L \
  -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36" \
  -H "Accept: image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8" \
  "URL_DE_LA_IMAGEN" \
  -o assets/ai/archivo.png
```

## 5. Problemas comunes

### `nodename nor servname provided, or not known`

El entorno no tiene DNS/red. En Codex hay que ejecutar el script con permiso de red real. Desde tu terminal normal deberia funcionar si tienes internet.

### `HTTP 403` con OpenAI `gpt-image-2`

Tu organizacion de OpenAI necesita verificacion para usar `gpt-image-2` directo. Verifica la organizacion en:

```text
https://platform.openai.com/settings/organization/general
```

Mientras tanto, usa DefAPI con `DEFAPI=...`.

### `HTTP 403 downloading DefAPI result: error code: 1010`

La tarea genero la imagen, pero la URL final bloqueo la descarga sin headers. El script ya descarga con `User-Agent` de navegador. Si lo haces manual, usa el ejemplo de `curl` de la seccion 4.

### `task not found`

Puede pasar justo despues de crear una tarea. El script lo tolera durante los primeros intentos porque DefAPI puede tardar unos segundos en indexar el `task_id`.

### `pending` por mucho tiempo

Espera unos minutos. Si sigue igual, consulta el `task_id` manualmente o vuelve a correr el script. Si vuelves a correrlo, se crean tareas nuevas y se consumen creditos otra vez.

## 6. Verificar archivos

Despues de generar:

```bash
file assets/ai/*.png
ls -lh assets/ai/*.png
```

Tambien puedes validar que el script no tenga errores de sintaxis:

```bash
python3 -m py_compile tools/generate_images.py
```

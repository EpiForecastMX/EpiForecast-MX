# Manual B1 — preparar Google Sheets y reanudar Tableau staging

## Objetivo

Desbloquear `C7.6-PROMOTION-ADAPTERS-B1-PREFLIGHT` sin publicar nada.

Este procedimiento:

- crea una hoja exclusiva de staging;
- entrega las credenciales únicamente por variables de entorno;
- permite que el agente inspeccione y genere el plan en modo read-only;
- no ejecuta `stage --apply`;
- no cambia lifecycle, puntero, DVC, Tableau Public, Netlify ni producción.

Estado que se retomará:

```text
backend               20e1ccdf
release               obesidad_release_2517e7858901
filas                 5,772
lifecycle             trained
validación            INCOMPLETE 0/4
gspread               6.2.1
google-auth           2.56.2
```

## Antes de empezar

Necesitas:

1. acceso a Google Sheets;
2. el archivo JSON de una service account;
3. el ID de la hoja productiva actual;
4. una terminal nueva;
5. entre 10 y 15 minutos.

No copies en un chat:

- el JSON;
- la private key;
- los IDs de las hojas;
- la ruta del archivo de credenciales.

## Paso 1 — identificar la service account

En tu terminal, fuera de los repositorios:

```zsh
jq -r '.client_email' /ruta/privada/service-account.json
```

Esto imprime únicamente el correo de la service account. El correo sirve para compartir la hoja y
no contiene la private key.

Si `jq` no existe:

```zsh
python3 -c 'import json; print(json.load(open("/ruta/privada/service-account.json"))["client_email"])'
```

No ejecutes comandos que impriman el JSON completo.

## Paso 2 — crear la hoja exclusiva de staging

1. Abre Google Sheets.
2. Crea una hoja nueva.
3. Ponle un nombre inequívoco, por ejemplo:

```text
EpiForecastMX — C7 Tableau STAGING — NO PUBLICAR
```

4. No copies la hoja productiva.
5. No la conectes a Tableau Public.
6. No agregues manualmente tabs `runner_*`.
7. Comparte la hoja con el correo de la service account como **Editor**.
8. No compartas una carpeta o Drive completo: sólo esta hoja.

La tab vacía que Google crea por defecto puede quedarse. El instalador la considera ajena y no
debe tocarla.

## Paso 3 — obtener los dos IDs

Una URL de Google Sheets tiene esta forma:

```text
https://docs.google.com/spreadsheets/d/ID_DE_LA_HOJA/edit
```

El ID es el texto entre `/d/` y `/edit`.

Necesitas dos IDs diferentes:

```text
C7_TABLEAU_STAGING_SPREADSHEET_ID   hoja nueva de staging
GSHEETS_SPREADSHEET_ID              hoja productiva existente
```

Si son iguales, detente. Nunca uses la hoja productiva como staging.

## Paso 4 — abrir una terminal nueva y cargar el entorno

```zsh
cd /Users/haowei/Documents/Integrador/EpiForecast-MX

export C7_TABLEAU_STAGING_SPREADSHEET_ID='ID_STAGING'
export GSHEETS_SPREADSHEET_ID='ID_PRODUCTIVO'
export GOOGLE_SERVICE_ACCOUNT_JSON="$(jq -c . /ruta/privada/service-account.json)"
```

La tercera variable contiene el JSON completo compactado. El código no acepta una ruta en lugar del
JSON.

Comprueba sólo presencia:

```zsh
for v in C7_TABLEAU_STAGING_SPREADSHEET_ID GSHEETS_SPREADSHEET_ID \
  GOOGLE_SERVICE_ACCOUNT_JSON; do
  if test -n "${(P)v}"; then
    echo "$v=present"
  else
    echo "$v=MISSING"
  fi
done
```

Las tres deben decir `present`. No uses `echo $GOOGLE_SERVICE_ACCOUNT_JSON`.

Comprueba que los IDs difieren sin mostrarlos:

```zsh
if test "$C7_TABLEAU_STAGING_SPREADSHEET_ID" = "$GSHEETS_SPREADSHEET_ID"; then
  echo "ERROR: staging y producción son la misma hoja"
else
  echo "OK: staging y producción son diferentes"
fi
```

## Paso 5 — iniciar una sesión nueva

Desde esa misma terminal:

```zsh
claude
```

Una sesión que ya estaba abierta no recibe exports hechos desde otra terminal.

Al iniciar, pega únicamente esta autorización:

```text
GO C7.6-PROMOTION-ADAPTERS-B1-PREFLIGHT-RESUME. Reanudar desde presencia de variables,
autenticación read-only, doble inspect, stage sin --apply y workbook temporal. STOP antes de
cualquier escritura Google, refresh con datos runner, DVC, push, lifecycle, puntero, deploy o
publicación.
```

No pegues valores ni credenciales.

## Paso 6 — qué debe ejecutar el agente

Ya no es una receta de varios comandos encadenados a mano: es **uno solo**, y el mismo que ya se
ejecutó en local sin credenciales.

```zsh
.venv/bin/python -m scripts.publication_readiness external-readonly \
  --local-evidence runs/readiness/<padecimiento>/readiness_manifest.json
```

Ese comando, y sólo ese, hace en este orden:

1. carga la evidencia local y exige que esté en `PASS_LOCAL`;
2. comprueba **presencia** de las tres variables y que staging ≠ producción, sin imprimir ninguna;
3. autentica **una vez** contra la hoja de staging;
4. inventaría dos veces y exige el mismo `inventory_digest`;
5. rechaza cualquier residuo `__next` o `__backup`;
6. enseña el plan de staging **en seco**;
7. regenera y verifica el workbook con el ID real de staging;
8. se detiene.

El carril local se cierra antes, sin nada de Google:

```zsh
make readiness DISEASE=<padecimiento> RELEASE=<ruta al bundle o su .dvc>
```

En esta fase no existe —ni en el CLI ni dentro del código— ninguna bandera, subcomando o llamada
equivalente a:

```text
--apply    recover    promote    delete
```

## Paso 7 — resultado esperado

Un PASS deja un artefacto junto al manifiesto local, y su digest se recomputa:

```text
runs/readiness/<padecimiento>/external_preflight.json    schema external_preflight.v1
```

Un `BLOCKED_EXTERNAL` o un `FAIL` **no** lo sobrescriben: la evidencia de un preflight que sí pasó
no se destruye por un intento posterior.

El reporte debe contener, sin secretos:

```text
gspread/google-auth versions
inventory_digest
states
foreign tabs
release_id
disease_id
operaciones propuestas
digest del candidate
digest del .twb
tableau_desktop_validated=false
hashes antes/después
```

El estado esperado antes de la primera escritura:

```text
tabs runner activas       0
residuos __next           0
residuos __backup         0
mutaciones Google         0
Obesidad                  trained
published_only            sin Obesidad
```

## Condiciones para detenerse

Detente y no intentes reparar la hoja si:

- falta una variable;
- los IDs coinciden;
- la service account no puede abrir la hoja;
- aparecen tabs `runner_*`;
- aparecen residuos `__next` o `__backup`;
- el dry-run propone una tab ajena;
- un error muestra cualquier fragmento de credenciales;
- el workbook contiene el ID productivo o Tableau Public.

## Errores comunes

### `falta C7_TABLEAU_STAGING_SPREADSHEET_ID`

La sesión no heredó el entorno. Cierra la sesión y vuelve a iniciarla desde la terminal donde
hiciste los exports.

### `PERMISSION_DENIED` o `SpreadsheetNotFound`

Comprueba que compartiste la hoja de staging con el `client_email` exacto de la service account.
No cambies permisos de la hoja productiva.

### `JSONDecodeError`

La variable no contiene JSON válido. Vuelve a cargarla con:

```zsh
export GOOGLE_SERVICE_ACCOUNT_JSON="$(jq -c . /ruta/privada/service-account.json)"
```

### `gspread` ausente

Desde el repo:

```zsh
.venv/bin/python -m pip install -e '.[gsheets]'
```

La instalación ya quedó hecha en el entorno auditado; sólo repítela si usas otro venv.

### La hoja contiene tabs `runner_*`

No ejecutes `recover` ni borres nada. Conserva la evidencia y pide una auditoría read-only.

## Al terminar la sesión

Cuando ya no necesites las credenciales:

```zsh
unset C7_TABLEAU_STAGING_SPREADSHEET_ID
unset GSHEETS_SPREADSHEET_ID
unset GOOGLE_SERVICE_ACCOUNT_JSON
```

Cerrar la terminal también elimina las variables de esa shell.

## Qué viene después

Un preflight PASS no publica nada. El siguiente paso requerirá otro GO:

```text
C7.6-PROMOTION-ADAPTERS-B1-APPLY
```

Ese paso escribirá únicamente en staging, releerá las tablas completas y recién entonces permitirá
abrir/refrescar el workbook en Tableau Desktop. Activación y deploy seguirán siendo autorizaciones
posteriores e independientes.

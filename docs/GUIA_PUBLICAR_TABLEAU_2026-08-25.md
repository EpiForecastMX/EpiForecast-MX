# Publicar Tableau desde tu cuenta — guía paso a paso

> Escrita el 25-ago-2026 tras auditar `reports/dashboards/NewVersionAug2026/`.
> Todo lo que aparece como «verificado» ya se comprobó: no hace falta que lo repitas.

## Fase 0 · Lo que ya está verificado (no tocar)

- **Tu workbook nuevo está bien de contenido.** 20 worksheets, `fecha_boletin` usado
  **248 veces** (antes eran 8) y **cero** `Week(` sin repuntar.
- **La hoja de Google productiva está viva y al día:**
  `https://docs.google.com/spreadsheets/d/1MahkA5xEsJwWdn9swge-h4pvQ3J3VePq1otT4xKjiYQ/edit`
  — `meta.updated = 2026-08-19 23:06:32 CST`, 2,711,102 celdas.
- **Esa hoja YA tiene `fecha_boletin`** en la pestaña `scaffold`
  (`ds, entidad, padecimiento, meta_modo, fecha_boletin`). Por eso reconectar **no** te va a
  romper los 248 usos.


## Cambio de hoja — 25-ago-2026, ejecutado

La hoja original vivía en una **unidad compartida (Shared drive)** de Google Workspace. El
conector de Drive de Tableau la listaba pero fallaba al leerla:

```
Bad Request: The data source does not contain the expected data. (A7AE75CC)
Google Drive has rejected this request because of insufficient permissions.
```

No es un problema del workbook ni del archivo: en una unidad compartida el dueño es la
organización, y una cuenta personal de Gmail no obtiene por API los permisos que el conector
necesita. Añadir un acceso directo no lo arregla.

**Solución aplicada: la hoja se mudó a un Drive que controlamos.**

| | |
| --- | --- |
| Hoja vigente | `tableau_epiforecast`, carpeta `EpiForecast_Tableau` de `javirebull@gmail.com` |
| ID vigente | `1yQ4tL7NzaUBplsoOfP9BVXARwUrb8h0i70vpDGvHpOQ` |
| ID anterior (rollback) | `1MahkA5xEsJwWdn9swge-h4pvQ3J3VePq1otT4xKjiYQ` |
| Variable de GitHub | `GSHEETS_SPREADSHEET_ID` actualizada el 25-ago-2026 |

**Copia verificada contra la original, dato a dato:**

| pestaña | filas | comprobación |
| --- | ---: | --- |
| `scaffold` | 227,106 | termina en **`fecha_boletin`** |
| `real` | 72,705 | |
| `forecast` | 227,106 | |
| `metricas` | 333 | |
| `entidades` | 37 | |
| `meta` | — | `updated = 2026-08-19 23:06:32 CST` |

**Cuentas de servicio con Editor en la hoja nueva** (las dos, porque el secreto
`GOOGLE_SERVICE_ACCOUNT_JSON` no es legible desde fuera y el nombre no basta para decidir):

- `epimx-sheets-drive@gen-lang-client-0524709190.iam.gserviceaccount.com`
- `github-actions-sheets@august-clover-453503-a9.iam.gserviceaccount.com`

**Copiar aquí NO es la trampa habitual**, porque se repuntó el pipeline a la copia. Copiar
sin repuntar habría dejado el tablero congelado en silencio: el Action seguiría escribiendo
en el ID viejo.

### Aviso sobre la «actualización automatizada»

`data/processed/tableau_model.xlsx` está **gitignorado** (11 MB) y ningún workflow lo
genera. Por tanto **`gsheets.yml` no puede correr solo**: fallaría al no encontrarlo. La
publicación a Google Sheets es hoy una operación **local y manual**. El sitio y la lámina 7
dicen «la actualización es automatizada» — eso es cierto de la descarga del boletín y de la
cadena de modelos, **no** de este último tramo. Deuda registrada.


## BLOQUEO: el conector de Google Drive no funciona (25-ago-2026)

**Descartado todo lo descartable, en este orden:**

1. Archivo en unidad compartida → se mudó a `My Drive` propio. **Sigue fallando.**
2. Acceso directo en vez de copia → irrelevante, el problema no era la ubicación.
3. Consentimiento de OAuth a medias → **era cierto en el primer intento**: la casilla «See
   and download all your Google Drive files» viene **desmarcada por defecto** en la pantalla
   nueva de Google y el botón *Continue* se deja pulsar igual. Se revocó y se volvió a
   conceder marcándola.
4. Permiso confirmado desde el lado de Google: `myaccount.google.com/connections` → Tableau
   → **«See and download all your Google Drive files»**, con los tres sub-permisos.
5. Token en caché → Tableau cerrado por completo y reabierto.

**Con todo lo anterior en verde, el conector sigue devolviendo:**

```
Bad Request: The data source does not contain the expected data. (A7AE75CC)
Google Drive has rejected this request because of insufficient permissions.
```

Entorno: **Tableau Desktop Public Edition 2025.3.2 (20253.26.0109.0333), Mac Apple silicon.**
La versión es reciente: no es el problema.

**Conclusión: es un fallo del conector, no de la configuración.** No insistir por clics.

## Decisión tomada: publicar con extracto

Se publica el workbook tal como está, con el extracto local. **Se gana hoy**: las 20
worksheets, los 248 usos de `fecha_boletin`, el tablero corregido y bajo la cuenta propia, y
el sitio funcionando.

**Se paga**: cada semana, tras `make tableau`, hay que **republicar el workbook** a mano.

**Y cuesta menos de lo que parece**, porque `gsheets.yml` no puede correr solo —el XLSX está
gitignorado— así que la cadena semanal ya era manual. La conexión viva a Google ahorraría
*un* paso de una rutina que ya se hace a mano.

**No se pierde nada del futuro:** reconectar a Google se puede hacer cualquier día sobre el
mismo workbook, sin rehacer las worksheets.

## Fase 1 · Reconectar la fuente (Tableau Desktop)

El único problema del workbook nuevo es que quedó apuntando a **Excel local + un extracto
`.hyper`**. Publicado así, el tablero se congela y deja de recoger el boletín semanal.

1. Abre **`reports/dashboards/NewVersionAug2026/viz_epiforecastmx.twb`**.
2. Añade la hoja como origen: **Datos → Nuevo origen de datos → Google Drive**, entra con tu
   cuenta y elige el spreadsheet de arriba. Trae las cinco pestañas:
   `scaffold`, `real`, `forecast`, `metricas`, `entidades`.
3. Reproduce las **relaciones sobre `ds`** tal y como están en el origen actual.
4. **Datos → Reemplazar origen de datos**: el viejo (Excel) por el nuevo (Google).
   Esto conserva las 20 worksheets y los campos, porque **los nombres de columna coinciden**.
5. Cierra el origen viejo y **quita el extracto**, para que la conexión quede en vivo.

> Si algún campo sale en rojo, es que el nombre no coincidió. No lo borres: renómbralo al
> nombre de la hoja. Perder un campo aquí es perder una worksheet.

## Fase 2 · Verificar antes de publicar

- Último real **`2026-W31`**, y **sin W32 real**.
- Los números **suman** (no hay dobles conteos por relación mal puesta).
- Los filtros responden.
- **Cero campos rojos y cero `Null` inesperados.**
- `fecha_boletin` aparece en las superficies visibles, **no** en las relaciones.

## Fase 3 · Guardar con nombre nuevo

Guarda como **`EpiForecastMX.twb`** (no `.twbx`: el `.twbx` empaqueta datos y vuelve a
congelar el tablero).

**Por qué cambiamos el nombre.** Hoy `viz_epiforecastmx` está publicado en Tableau Public
bajo la cuenta **`luis.sanchez.salazar`** — comprobado: la URL antigua responde `302` hacia
su perfil. Si publicas con el mismo nombre desde tu cuenta habría **dos workbooks llamados
igual** y el sitio seguiría enseñando el de Luis. Con un nombre nuevo, la resolución es
inequívoca y **no dependemos de que nadie borre nada**.

## Fase 4 · Publicar desde tu cuenta

1. **Servidor → Tableau Public → Guardar en Tableau Public**, con **tu** sesión.
2. Nombre de la vista: **`EpiForecastMX`**.
3. Cuando termine, copia de la barra del navegador la URL de una vista. Debe verse así:
   `https://public.tableau.com/app/profile/TU_PERFIL/viz/EpiForecastMX/DashNacional`

## Fase 5 · Pásame dos datos

1. **Tu perfil** de Tableau Public (el trozo `TU_PERFIL` de la URL).
2. **Confirmación del nombre** final del workbook.

Con eso actualizo los **diez embeds** de `EpiDashboard.html`. Son estos, y sólo cambia la
parte del workbook:

| # | vista | # | vista |
| --- | --- | --- | --- |
| 1 | `Tabladedatos` | 6 | `DashNacional` |
| 2 | `MapadeMxico` | 7 | `DashRegional` |
| 3 | `Mxicoencategoras` | 8 | `DashDesempeno` |
| 4 | `Casosporao` | 9 | `Predicciones` |
| 5 | `Casosporsemana` | 10 | `DashKPIs` |

## Fase 6 · El sitio (lo hago yo)

Rama nueva, PR y despliegue: cambio `name` y `static_image` en los diez bloques. Producción
ya está desplegada y con una sola rama, así que es un cambio limpio.

## Fase 7 · Smoke test conjunto

- `EpiDashboard.html` en **ventana privada**: las diez vistas cargan.
- La fecha visible es **W31**.
- No declarar PASS porque Tableau aceptó la subida: hay que **verlo cargado en el sitio**.

## Después (autorización aparte)

- Decidir si `NewVersionAug2026/` entra al repositorio (3,5 MB, hoy sin trackear).
- Respaldo postpublicación y reducir el permiso de la cuenta de servicio.
- La vieja vista de Luis puede quedarse: con el nombre nuevo ya no estorba.

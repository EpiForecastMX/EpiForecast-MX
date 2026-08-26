# Estado operativo — Google Sheets y Tableau W31

> Actualizado el **2026-08-25**. Registra el carril legacy neuro de Tableau; no autoriza ni
> modifica el lifecycle C7 de Obesidad.

## Qué cambió el 25-ago

El usuario abrió Tableau y rehízo el workbook. El resultado está en
`reports/dashboards/NewVersionAug2026/` (**sin trackear en git**):
`viz_epiforecastmx.twb` (2,0 MB), su carpeta `… Files/Data`, y `viz_epiforecastmx.twbx`
(1,5 MB).

**Auditado leyendo el XML —no hace falta abrir Tableau para esto—:**

| Requisito del plan anterior | Estado |
| --- | --- |
| 20 worksheets completas | **✔** 20 |
| `fecha_boletin` en superficies visibles | **✔** 248 apariciones (antes 8 en `W31_REPARADO`) |
| Los `Week(ds)` repuntados | **✔** cero `Week(` en el XML |
| Fuente final = Google Sheet productivo | **✖ NO.** `excel-direct` + extracto `hyper`; **cero** referencias a google/drive |

Es decir: **el contenido ya está bien y el trabajo pesado está hecho.** Lo que falta es la
conexión.

## El bloqueo real: la fuente quedó local

El `.twbx` empaqueta `Data/tableau-temp/#TableauTemp_….hyper` (1,2 MB). Publicar eso deja
una **foto congelada**: el tablero dejaría de recoger el boletín de la semana siguiente.

Eso **contradice lo que decimos en público** —lámina 7 del congreso y el sitio: «la
actualización es automatizada; la publicación requiere validación humana»—. Con un extracto
empaquetado, la primera parte deja de ser cierta para la superficie de Tableau.

**Antes de publicar hay que reconectar la fuente al Google Sheet productivo** y volver a
guardar. El resto del trabajo (los 248 usos de `fecha_boletin`) se conserva.

## La cuenta: comprobado en vivo el 25-ago

La vista publicada hoy resuelve por redirección a:

```
https://public.tableau.com/views/viz_epiforecastmx/DashNacional
  → 302 → .../app/profile/luis.sanchez.salazar/viz/viz_epiforecastmx/DashNacional
```

Es decir, **el workbook público lo tiene hoy la cuenta de Luis Gerardo Sánchez-Salazar**.

Y los diez embeds de `EpiDashboard.html` **no llevan nombre de cuenta**: `site_root` va
vacío y `name` es sólo `viz_epiforecastmx/DashNacional`. Funcionan porque Tableau resuelve
ese nombre a la cuenta que lo publicó.

**Consecuencia si se publica desde otra cuenta:** habría dos workbooks con el mismo nombre
en Tableau Public y **el sitio seguiría enseñando el de Luis**, o la resolución quedaría
ambigua. No basta con subirlo.

### Las dos salidas, y cuál recomiendo

1. **Publicar desde la cuenta que ya lo tiene** (`luis.sanchez.salazar`), sobrescribiendo.
   El sitio no se toca y nada se rompe. **Es la vía limpia** si esa cuenta sigue disponible.
2. **Publicar desde la cuenta nueva** — entonces hay que **actualizar los diez embeds** de
   `EpiDashboard.html` con la ruta de perfil explícita, y **retirar o renombrar** el
   workbook viejo para que no queden dos. Es un cambio en el repositorio del sitio, con su
   PR y su despliegue.

## Siguiente sesión — secuencia exacta

1. Abrir `NewVersionAug2026/viz_epiforecastmx.twb` en Tableau Desktop.
2. **Reconectar la fuente al Google Sheet productivo** (hoy apunta a Excel local + extracto).
   No editar por cirugía XML.
3. Verificar que las relaciones siguen sobre `ds` y que `fecha_boletin` sólo se usa en
   superficies visibles.
4. Verificar localmente: último real `2026-W31`, sin W32 real, números agregables, filtros
   vivos, cero campos rojos o `Null`.
5. Guardar una copia final distinta de los borradores.
6. **Decidir la cuenta** con el criterio de arriba antes de subir nada.
7. Publicar/sobrescribir `viz_epiforecastmx`.
8. Smoke test en ventana privada. **No declarar PASS porque Tableau aceptó el upload:**
   comprobar que `EpiDashboard.html` carga las diez vistas y que la fecha es W31.
9. Respaldo postpublicación y reducir el permiso de la cuenta de servicio.
10. Autorización separada para Git/DVC. Los archivos de `NewVersionAug2026/` **siguen sin
    trackear**: decidir si entran al repositorio (3,5 MB) o quedan fuera.

## Google Sheets productivo

La publicación directa se ejecutó por overrule explícito del protocolo B1, que exigía staging.
El riesgo aceptado era una actualización no transaccional, pestaña por pestaña. Se protegió con
respaldo tipado, guard de identidad y restauración con relectura completa.

Estado público comprobado:

| Superficie | Filas | Columnas | Observación |
| --- | ---: | ---: | --- |
| `scaffold` | 227,106 | 5 | incluye `fecha_boletin` |
| `real` | 72,705 | 6 | `ds.max() = 2026-07-20` |
| `forecast` | 227,106 | 5 | `yhat` numérico |
| `metricas` | 333 | 10 | métricas numéricas |
| `entidades` | 37 | 12 | población y densidades numéricas |
| `meta` | — | — | `updated = 2026-08-19 23:06:32 CST` |

Total: **2,711,102 celdas**. Las cinco tablas públicas coinciden con el XLSX local. Google
Visualization redondea `densidad_poblacion` al mostrarla; la diferencia máxima observada fue
menor a `6e-8` y no representa drift del valor almacenado.

Candidato local que originó la hoja publicada:

- ruta: `data/processed/tableau_model.xlsx`;
- SHA256: `a0141391bfebd0715a9573d49575ff660b49bd12c9b517691f35bd184a6e18a7`;
- `fecha_boletin = ds + 7 días` en el 100 % de `scaffold`;
- última realidad: `ds=2026-07-20` → `fecha_boletin=2026-07-27` → W31;
- cohorte exacta: Alzheimer, Depresión y Parkinson;
- cero Obesidad y Anorexia.

El gate `scripts/verifica_tableau_fecha_boletin.py`, Ruff y formato pasan. El cambio funcional
está en `scripts/build_tableau.py` y es aditivo: `fecha_boletin` no participa en relaciones.

## Rollback disponible

El estado anterior a la publicación se conserva como JSON tipado:

- copia de trabajo: `respaldos_gsheets/2026-08-20_tipado_W31/`;
- copia externa: `~/Documents/Respaldos_EpiForecast/gsheets_2026-08-20_W31/`;
- ambas copias coinciden por hash;
- `restaura_gsheets.py` rechaza respaldos no tipados, valida todos los hashes antes de
  escribir, sólo acepta el ID consignado y relee cada pestaña después de restaurarla.

No reemplazar ese respaldo por uno posterior: es el punto de retorno prepublicación.

## Lección operativa pendiente

El publicador legacy borra y escribe pestaña por pestaña, sin transacción ni retry/backoff.
Durante esta actualización se encontró el límite `429 write requests per minute`. Antes de la
próxima actualización hay que añadir reintentos con espera, checkpoint por pestaña y una
verificación automática final; no depender otra vez de completar manualmente una escritura
parcial.

## Deudas que quedan anotadas

1. El backend está en `main`, detrás de `origin/main` por un commit, con cambios y archivos del
   usuario. No cambiar de rama ni limpiar el worktree sin preservar ese estado.
2. `scripts/build_tableau.py` está modificado y
   `scripts/verifica_tableau_fecha_boletin.py` está sin rastrear.
3. `data/processed/tableau_model.xlsx.dvc` reporta el XLSX modificado: un clon limpio aún no
   reconstruye los bytes publicados.
4. El publicador necesita retry/backoff y reanudación segura antes del próximo boletín.
5. Tableau Public no se ha refrescado ni validado con W31/`fecha_boletin`.
6. Los borradores Tableau y el `.hyper` pertenecen al usuario y no deben añadirse ni borrarse
   por inferencia.

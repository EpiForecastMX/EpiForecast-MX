**Caso A: pasa la evidencia operativa de extracción. Caso B: no pasa; la pasada 2 falló y su CSV no salió de esa corrida.** No ejecuté nada: comparé los archivos por lectura y no recalculé ningún sha256 (los hashes son los declarados en `EJECUCION.json`).

## Caso A

| Evidencia | Resultado |
| --- | --- |
| Inventario | Pasa: cada manifiesto cubre exactamente los 3 PDF de `INVENTARIO.json`, sin duplicados ni omisiones. |
| Manifiesto | Pasa: los 3 en `ok` con 32 entidades, sin exclusiones que declarar. |
| Contenido | Pasa: 96 filas (3 semanas por 32 entidades), sin ceros masivos ni duplicados; en las filas que revisé el acumulado H+M avanza igual que `Casos_semana`. |
| Frescura | Pasa frente al corte declarado: el CSV llega a la semana 3, último PDF del inventario. |
| Dos corridas | Pasa: mismo `code_snapshot`, config con el mismo hash al inicio y al fin, salidas exclusivas distintas, CSV y manifiesto escritos dentro de la ventana de cada corrida y mismo `csv_sha256`. |

- **Conclusión:** el determinismo queda acreditado para este corte y este snapshot de código y configuración.
- **Lo que no prueba:** las dos pasadas declaran la misma ventana horaria (corrieron en paralelo) y el fixture no dice si usaron árboles de trabajo separados. Lo acepto porque config y salidas constan como inmutables y exclusivas.
- **Siguiente paso:** copiar el CSV tal cual a `data/raw/data_raw_<artifact_key>.csv`, recalcular y anotar su sha256 (debe dar `1abfb0fe…`) y correr `validate-data`. No autoriza nada más allá de eso.

## Caso B

| Evidencia | Resultado |
| --- | --- |
| Pasada 1 | Válida por sí sola: misma evidencia que en el caso A. |
| Manifiesto de la pasada 2 | Falla: los 3 PDF en `error` (`ConstructorError: duplicate YAML key`) con 0 entidades. |
| CSV de la pasada 2 | Falla: su `csv_mtime` es una hora anterior al inicio de la corrida, mientras el manifiesto sí es de la corrida. Es un archivo previo. |
| Código de salida | `wrapper_rc: 0` pese a los tres errores: no sirve como gate. |
| Dos corridas | No acreditadas: el sha256 coincide porque se comparó un CSV que la pasada 2 no produjo. |
| Frescura | Sólo consta para la pasada 1. |

- **Conclusión:** hay una sola corrida válida; no hay determinismo demostrado y no se prepara el raw.
- **Causa, sin medir:** el fixture no dice qué YAML tiene la clave duplicada. La pasada 1 terminó bien con el mismo `config_sha256`, así que ese hash podría no cubrir el archivo que falla, o el entorno difirió entre pasadas. Ambas son hipótesis.
- **Siguiente paso** (cubierto por la autorización de correcciones ordinarias):
  1. Localizar y corregir la clave duplicada, y dejar el cambio en un snapshot inmutable.
  2. Corregir el envoltorio para que aparte o verifique la salida previa y no devuelva 0 con el manifiesto en error.
  3. Repetir **las dos** pasadas sobre ese snapshot, cada una con salida exclusiva y limpia. La pasada 1 actual deja de servir como pareja si cambian código o configuración.
  4. Volver a revisar inventario, manifiesto, fechas de escritura y sha256 antes de copiar nada a `data/raw/`.
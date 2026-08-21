# Qué hacer en CMT — MICAI 2026, ponencia #12

**Fecha límite: domingo 23 de agosto, fin del día AoE** (≈ 24-ago 06:00 hora del centro
de México). Hoy es jueves 20: quedan **3 días**.

La carta de aceptación pide que los nombres y las afiliaciones sean correctos **en el paper
y en CMT**. Hoy no coinciden. Estos son los valores a los que hay que llevar CMT.

---

## 1. Los valores exactos

Cópialos tal cual. Ojo con dos cosas: **el guion** en los apellidos compuestos, y que
**«Tecnologico» va sin acento** — no es un descuido, es lo que exige el lineamiento
TEC-II-05 del Tec para que Scopus indexe bien.

| # | Nombre en CMT hoy | **Debe decir** | Organization hoy | **Debe decir** |
|---|---|---|---|---|
| 1 | Javier Rebull Saucedo | **Javier Augusto Rebull-Saucedo** | ITESM | **Tecnologico de Monterrey** |
| 2 | Juan Pérez Nava | **Juan Carlos Pérez-Nava** | ITESM | **Tecnologico de Monterrey** |
| 3 | Luis Sánchez Salazar | **Luis Gerardo Sánchez-Salazar** | ITESM | **Tecnologico de Monterrey** |
| 4 | Grettel Barceló Alonso | **Grettel Barceló-Alonso** | ITESM | **Tecnologico de Monterrey** |
| 5 | Ruth Pérez Hernández | **Ruth Pérez-Hernández** | IMSS | **Instituto Mexicano del Seguro Social, Órgano de Operación Administrativa Desconcentrada Estatal Guerrero** |

> **Nombres de pila completos.** Springer los pide completos y así los registran los
> ORCID públicos de los tres. La portada ya dice Javier Augusto, Juan Carlos y Luis
> Gerardo; CMT, la licencia firmada y el README del repositorio citado tienen que
> decir exactamente lo mismo, carácter por carácter.

Los correos **no se tocan**: los cinco ya coinciden con el paper, incluido el de Ruth con
punto (`ruth.perezher@imss.gob.mx`).

El orden de los autores **tampoco se toca**: ya es el correcto.

---

## 2. Los pasos

1. Entra a `cmt3.research.microsoft.com` → **Author Console** → selecciona **MICAI2026**.
2. Localiza la ponencia **#12**.
3. Busca la acción de editar. Según cómo tengan configurado el ciclo, verás una de dos:
   - **«Edit Submission»** en la fila de la ponencia, o
   - la página de **Camera Ready Submission**, que suele traer el bloque de autores arriba
     del área de carga del archivo.
4. En el bloque de autores, corrige nombre y organización de cada uno según la tabla.
5. Guarda.

### Si los campos de nombre aparecen bloqueados

Es lo más probable, y no es un error: **CMT toma el nombre y la organización del perfil de
cada usuario**, no de la ponencia. Entonces:

- **Tu propio nombre** lo cambias tú: arriba a la derecha, tu nombre → **Edit Profile** →
  corrige *Last Name* a `Rebull-Saucedo` y *Organization* a `Tecnologico de Monterrey` →
  guarda. El cambio se refleja solo en la ponencia.
- **Los otros cuatro** tienen que entrar cada quien a su cuenta y hacer lo mismo en su
  propio *Edit Profile*. Mándales las dos líneas que les toquen de la tabla.
- Sólo la organización suele ser editable desde la ponencia; el nombre casi nunca.

### Si nada es editable

Escribe a los chairs —**Gilberto Ochoa-Ruiz** e **Iris Mendez**, por el sistema de
contacto de CMT— explicando que son correcciones de **ortografía y afiliación**, no un
cambio de autoría: son las mismas cinco personas, en el mismo orden. Springer no permite
cambiar la autoría después del camera-ready, y por eso conviene resolverlo **antes** de
subir el paquete.

---

## 3. Subir el paquete

Una vez que CMT coincida con el paper:

- Sube **`Congresos/MICAI/Envio/012.zip`** en la sección de camera-ready.
- Es el único archivo del paquete: lleva dentro `012.tex`, `llncs.cls`, `splncs04.bst`,
  las tres figuras y `012.pdf`. Ya está verificado compilándolo desde el propio ZIP:
  20 páginas, A4, sin errores.
- No subas la carpeta suelta ni el `.tex` por separado: MICAI acepta LaTeX **sólo** como
  `.zip`.

---

## 4. Lo demás que pide la carta

- **Licencia LNAI** — descarga `LNAI_license_to_publish_MICAI2026_maintrack.docx` de
  `micai.org/2026/authors/`, la firmas **tú** como autor de correspondencia, y la subes
  donde CMT la pida.
- **Registro** — al menos un autor debe registrarse en `micai.org/2026/#registration`.
  Sin esto el paper se retira de las actas, aunque el camera-ready esté entregado.
  **Pero no esperes al registro para subir el ZIP**: el registro temprano abre el 24 de
  agosto —un día *después* del camera-ready— y el pago vence el 16 de octubre. Sube
  primero el paquete; el registro se completa después.

---

## 5. Guarda el comprobante y el hash

Al terminar la carga, descarga o captura el acuse de CMT y guárdalo junto a
`Envio/HASH_ENVIO.txt`. Ese archivo tiene el sha256 del paquete:

```
1bfec014a83ed22efc79fbd967ab86b373a9a30ccb234a9fa68dfbfaed8b5a99
```

Compruébalo antes de subir — este control falla si el ZIP y los documentos no
coinciden, que es como se desincronizaron la primera vez:

```
.venv/bin/python scripts/paper_micai_2026/sello_sincronizado.py
```

El ZIP se construye de forma determinista, así que ese hash identifica el **contenido**:
si algún día hay que demostrar qué se envió, se reconstruye y tiene que dar el mismo valor.

---

## 6. Avísame cuando termines

Con la captura de CMT ya corregida vuelvo a verificar que la cabecera del paper coincida
exactamente, letra por letra, antes de que subas el ZIP.

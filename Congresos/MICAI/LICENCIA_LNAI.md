# Licencia LNAI — qué hacer, ponencia #12

**Estado: descargado**, en
`DocusMICAI/LNAI_license_to_publish_MICAI2026_maintrack.docx` (59 KB, versión
`v.2.0.1 12_2025`). Estaba en `micai.org/docs/`, no en la página de autores.
**Falta llenarlo y firmarlo.**

---

## Aviso del comité editorial (14-ago-2026)

> «when completing the Copyright Form, the section at the bottom labeled **“Edition ID /
> IPS”** should not be filled in by the authors. This information will be completed by the
> editor, so please leave these fields blank.»

**Deja "Edition ID / IPS" en blanco.** Lo llena el editor.

---

## Reglas de Springer que aplican aquí

Del instructivo oficial (`reference_material/Instructions+for+proceedings+authors+(pdf).pdf`):

- **«Digital signatures are not acceptable»** (§5.1). Hay que **imprimir, firmar a mano y
  escanear**. Una firma insertada como imagen o un PDF firmado digitalmente no sirven.
- **Un solo autor de correspondencia por paper**, y debe **coincidir con el marcado en la
  cabecera**. En el paper es Javier, con asterisco, la nota «Corresponding author.» y
  `rebull@outlook.com`. ✔
- El autor de correspondencia firma **en nombre de todos** y debe tener autoridad para
  hacerlo. Confírmalo con los otros cuatro antes de firmar.
- Si algún autor está sujeto a un régimen especial (empleo gubernamental, Crown
  Copyright), puede necesitar un formato distinto — y puede hacer falta **más de una
  licencia por paper**. **Ruth es del IMSS**: vale la pena preguntarle si el IMSS exige
  algún trámite propio. Springer avisa que los problemas de copyright sin resolver
  retrasan la publicación bastante.

---

## Dos cosas que ya cumplimos sin saberlo

**§5.2 — apellidos compuestos.** Springer pide literalmente: *«If you or any of your
co-authors have more than one family name, it should be made quite clear how your name is
to be displayed in the running heads and the author index.»* El guion es justo el
mecanismo, y `\authorrunning{J.A. Rebull-Saucedo et al.}` lo deja explícito para el titulillo.
**El paper ya hace lo que pide esa sección**, y eso refuerza el correo a los chairs.

**§5.2 — nombres completos.** Pide que los nombres vayan *«written out in full»*, sin
iniciales. Esto lo teníamos MAL y se corrigió el 21-ago-2026: la portada llevaba `Javier`,
`Juan` y `Luis`, que no son los nombres completos sino formas cortas. Los ORCID públicos
registran **Javier Augusto**, **Juan Carlos** y **Luis Gerardo**, y así va ahora la portada.
CMT, esta licencia y el README del repositorio citado tienen que decir exactamente lo mismo,
carácter por carácter: si la licencia firmada lleva un nombre y la portada otro, Springer
para la producción.

**§5.3 — ORCID.** Pide incluirlo en la cabecera; en el libro impreso se sustituye por el
icono de ORCID. Los cinco ya están puestos con `\orcidID`. ✔

---

## Verificado contra los documentos oficiales (20-ago-2026)

Descargados en `DocusMICAI/`: instructivo de autores y los dos templates.

- **`llncs.cls` y `splncs04.bst` del paper son BYTE-IDÉNTICAS a las oficiales**
  (`a3cfe775…`, 43 402 bytes y 32 146 bytes). La clase que compila el camera-ready es la
  que Springer distribuye, sin parches.
- El instructivo nuevo (10 pág.) **no es el mismo archivo** que el que ya teníamos
  (11 pág.), pero **§5.1, §5.2 y §5.3 son idénticas palabra por palabra**. Lo único que
  cambia de fondo es un párrafo sobre guardar el template de Word como `.docx` y nunca
  como `.docm` — no aplica, vamos en LaTeX.
- **§4.2**: los *full papers* son de 12–15 páginas «o más». Nuestras 20 caben dentro del
  techo de MICAI.

**El formato de licencia SÍ está descargado**, en
`DocusMICAI/LNAI_license_to_publish_MICAI2026_maintrack.docx`. No aparecía en la página de
autores sino en `micai.org/docs/`, que es lo que despistó. Lo que falta es **llenarlo y
firmarlo a mano**, no conseguirlo.

---

## Orden

1. Abrir el `.docx` que ya está en `DocusMICAI/` (no hay que descargar nada).
2. Llenarlo — título y autores tal como aparecen en el paper, **«Edition ID / IPS» en blanco**.
3. Imprimir, **firmar a mano**, escanear.
4. Preguntar a Ruth si el IMSS requiere algo adicional.
5. Subirlo a CMT en su campo, junto con `012.zip`.

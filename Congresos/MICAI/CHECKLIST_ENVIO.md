# Checklist de envío — MICAI 2026, ponencia #12

Límite: **domingo 23-ago-2026, fin del día AoE.**
El ZIP y la licencia van por el mismo canal y en el mismo momento. Sin la licencia
firmada el camera-ready no queda completo aunque el ZIP esté cargado.

---

## 0 · Antes de nada, lo que depende de otra persona

- [ ] **Ruth ya aprobó su afiliación tal como va impresa**, carácter por carácter:
      `Instituto Mexicano del Seguro Social, OOAD Guerrero, Mexico`
      Si su firma lleva una forma y la portada otra, Springer para la producción.
- [ ] Preguntarle si el IMSS exige algún trámite adicional para la licencia.

---

## 1 · La licencia LNAI

El archivo ya está descargado; no hay que buscarlo:
`Congresos/MICAI/DocusMICAI/LNAI_license_to_publish_MICAI2026_maintrack.docx`

- [ ] Título **exacto** del paper:
      *Forecasting Weekly Depression Incidence in Mexico: A Multi-Model Framework
      with Auditable Per-Series Model Selection*
- [ ] Los cinco autores, en orden y con los nombres completos:
      Javier Augusto Rebull-Saucedo · Juan Carlos Pérez-Nava ·
      Luis Gerardo Sánchez-Salazar · Grettel Barceló-Alonso · Ruth Pérez-Hernández
- [ ] Corresponding author y *Print Name*: **Javier Augusto Rebull-Saucedo**
- [ ] Fecha, dirección postal y `rebull@outlook.com`
- [ ] **«Edition ID / IPS» EN BLANCO.** Lo llena el editor de Springer; el instructivo
      oficial pide explícitamente que los autores no lo toquen.
- [ ] Imprimir y **firmar a mano** (Javier firma en nombre de los cinco)
- [ ] Escanear **todas** las páginas, legibles

---

## 2 · El gate, justo antes de cargar

```bash
cd ~/Documents/Integrador/EpiForecast-MX
.venv/bin/python scripts/paper_micai_2026/sello_sincronizado.py
```

- [ ] Termina en **`VEREDICTO: PASA`**

Comprueba que el ZIP y todo lo que los documentos dicen de él coinciden — hash y
tamaño. Si sale FALLA, **no subas nada**: algo se movió desde el sellado.

Debe corresponder a:

```
Congresos/MICAI/Envio/012.zip
849d5451b11918c21be0807cffbd3749c7b77edb305ccab94d1748eb535fda2b
701 541 bytes
```

---

## 3 · La carga en CMT

- [ ] `012.zip` en el campo **Camera Ready Submission**
- [ ] El escaneo de la licencia firmada, en **su campo separado**
- [ ] **Finalizar la submission de verdad** — que no quede en borrador
- [ ] Si CMT permite descargar lo enviado, bájalo y vuelve a comprobar su hash

### Lo que NO se sube

`012_overleaf.zip` · `paper_submission.pdf` · el PDF suelto · `HASH_ENVIO.txt` ·
auditorías, planes o scripts · el bundle de respaldo · nada de CALASS ·
capturas del correo a los chairs.

---

## 4 · Después de subir

- [ ] Guardar el acuse o captura junto a `Congresos/MICAI/Envio/HASH_ENVIO.txt`
- [ ] Guardar ahí también una copia del escaneo de la licencia
- [ ] **No editar ni reempaquetar nada.** Recompilar es inocuo —la compilación es
      reproducible y da el mismo hash—, pero tocar el `.tex`, una figura o la clase
      hace que lo que tengas en disco deje de ser lo que entregaste.

---

## 5 · Seguimiento, ya sin prisa

- [ ] Respuesta de los chairs sobre los metadatos de CMT. Se les escribió el
      21-ago-2026 por *Email Chairs* con acuse: la sección autoral está bloqueada y
      hay que corregir nombres completos y afiliaciones. Si contestan proponiendo
      conservar «ITESM», se declina citando el lineamiento TEC-II-05.
- [ ] Un remoto privado **fuera de la máquina**. El bare local en `BK/` y el bundle
      autocontenido cubren el error humano, no la pérdida del disco.
- [ ] Tras la publicación de Springer: añadir el DOI al repositorio público y
      archivar el release del código.

---

## Lo que ya está hecho, para que no lo repitas

- Paquete verificado compilándolo **desde dentro del ZIP**; su PDF coincide con el
  canónico salvo el `/ID`, que pdfTeX deriva del nombre del fichero.
- 20 páginas A4 · 27/27 pruebas · 45 comprobaciones del paquete · 9 gates.
- Cero fuentes Type 3; las 33 incrustadas.
- El repositorio que el paper cita reproduce la Tabla 3 desde un clon limpio, y su
  URL responde 200 directo, sin redirección.
- Correo a los chairs enviado, con acuse de CMT.

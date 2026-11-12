#!/bin/bash
# Consulta el índice oficial y falla si hay un boletín posterior al 43 de 2026 (formatos semNN.pdf y
# Boletin-NN26.pdf) o si cambia el número de adjuntos (43).
D=/tmp/epiforecast-alta10b-20261112/indices; mkdir -p $D
T=$(date -u +%Y%m%dT%H%M%SZ)
curl -s -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36" -H "Accept-Language: es-MX" "https://www.gob.mx/salud/documentos/boletinepidemiologico-sistema-nacional-de-vigilancia-epidemiologica-sistema-unico-de-informacion-417103" -o $D/indice_$T.html -w "%{http_code}" > $D/indice_$T.code
code=$(cat $D/indice_$T.code)
a=$(grep -oE 'attachment/file/[0-9]+/[^"]+\.pdf' $D/indice_$T.html | sort -u)
n=$(echo "$a" | grep -c pdf)
m1=$(echo "$a" | grep -oE 'sem([0-9]+)\.pdf' | grep -oE '[0-9]+' | sort -n | tail -1)
m2=$(echo "$a" | grep -oE 'Boletin-([0-9]{2})26\.pdf' | grep -oE '[0-9]{4}' | cut -c1-2 | sort -n | tail -1)
max=$(printf "%s\n%s\n" "$m1" "$m2" | sort -n | tail -1)
echo "$T http=$code adjuntos=$n ultimo=$max sha=$(shasum -a 256 $D/indice_$T.html | cut -c1-16)" | tee -a $D/registro.txt
[ "$code" = "200" ] && [ "$max" = "43" ] && [ "$n" = "43" ]

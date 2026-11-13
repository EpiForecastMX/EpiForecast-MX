#!/bin/bash
# Desarrollo con la política autorizada (B2/B14) sobre el raw canónico; sin abrir 2025.
cd /tmp/epiforecast-alta10b-20261112
for id in "$@"; do
  scripts/model_dev.sh $id canon > model/dev5_$id.out 2>&1; rc=$?
  echo "$(date -u +%H:%M:%SZ) $id dev5 rc=$rc $(tail -1 model/dev5_$id.out)" >> logs/dev5.status
done
echo DONE >> logs/dev5.status

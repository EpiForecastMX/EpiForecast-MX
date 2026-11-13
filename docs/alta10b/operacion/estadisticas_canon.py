"""Estadísticas descriptivas del raw canónico (extract/canon/<id>_boletin.csv) para la propuesta de
política: mediana estatal semanal 2021-2024, % de semanas en cero por entidad, nacional semanal y
casos por año fuente. Salida qa/<id>_estadisticas.json con el sha256 del raw."""
import hashlib, json, sys
import pandas as pd
i = sys.argv[1]; p = f'extract/canon/{i}_boletin.csv'
d = pd.read_csv(p, dtype={'Semana': str}); d['Casos_semana'] = pd.to_numeric(d['Casos_semana'], errors='coerce')
z = d[(d.Anio >= 2021) & (d.Anio <= 2024)]
med = z.groupby('Entidad')['Casos_semana'].median(); ceros = z.groupby('Entidad')['Casos_semana'].apply(lambda x: float((x == 0).mean() * 100))
nac = z.groupby(['Anio', 'Semana'])['Casos_semana'].sum()
out = {'id': i, 'raw': p, 'raw_sha256': hashlib.sha256(open(p, 'rb').read()).hexdigest(),
       'mediana_estatal_2021_2024': {'mediana': float(med.median()), 'p10': float(med.quantile(.1)), 'min': float(med.min())},
       'pct_semanas_cero_por_entidad_2021_2024': {'mediana': float(ceros.median()), 'entidades_mas_de_50pct': int((ceros > 50).sum())},
       'nacional_semanal_2021_2024': {'mediana': float(nac.median()), 'semanas': int(len(nac))},
       'casos_por_anio_fuente': {int(k): int(v) for k, v in d.groupby('Anio')['Casos_semana'].sum().items()}}
json.dump(out, open(f'qa/{i}_estadisticas.json', 'w'), ensure_ascii=False, indent=1); print(i, out['raw_sha256'][:12])

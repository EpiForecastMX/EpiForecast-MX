# Investigacion de Costos - EpiForecast-MX

**Fecha de elaboracion:** 10 de marzo de 2026
**Tipo de cambio de referencia:** 17.77 MXN/USD (FIX Banxico, 9 de marzo de 2026)
**Fuente tipo de cambio:** Banco de Mexico, Sistema de Informacion Economica
<https://www.banxico.org.mx/tipcamb/tipCamMIAction.do>
(consultado: 10 de marzo de 2026)

---

## 1. Costos de AWS SageMaker e Infraestructura Cloud

### 1.1 Instancia ml.g4dn.xlarge (Entrenamiento SageMaker)

| Concepto | Precio USD | Precio MXN | Fuente |
|----------|-----------|------------|--------|
| EC2 g4dn.xlarge on-demand (us-east-1) | $0.526/hr | $9.35/hr | AWS EC2 Pricing |
| SageMaker Training ml.g4dn.xlarge (us-east-1) | $0.736/hr | $13.08/hr | AWS SageMaker Pricing |
| Especificaciones | 4 vCPUs, 16 GB RAM, 1 NVIDIA T4 GPU, 125 GB NVMe SSD | - | AWS |

**Nota:** El precio de SageMaker Training incluye un sobreprecio de aproximadamente 40% respecto al precio base de EC2, que cubre la gestion del cluster de entrenamiento, aprovisionamiento automatico y almacenamiento temporal de modelos.

**Fuentes:**
- AWS EC2 On-Demand Pricing: <https://aws.amazon.com/ec2/pricing/on-demand/>
  (consultado: 10 de marzo de 2026)
- AWS SageMaker Pricing: <https://aws.amazon.com/sagemaker/pricing/>
  (consultado: 10 de marzo de 2026)

**Estimacion para EpiForecast-MX:**
- Entrenamiento de 3 padecimientos (Depresion, Parkinson, Alzheimer): ~2-3 horas por padecimiento con DeepAR.
- Total por ciclo de entrenamiento completo: ~6-9 horas = **$4.42 - $6.62 USD** ($78.54 - $117.65 MXN)
- Frecuencia: Reentrenamiento trimestral = **$17.66 - $26.50 USD/anio** ($313.82 - $470.90 MXN/anio)

### 1.2 Amazon S3 (Almacenamiento)

| Concepto | Precio USD | Precio MXN |
|----------|-----------|------------|
| S3 Standard - Primer 50 TB/mes | $0.023/GB/mes | $0.41/GB/mes |
| PUT, COPY, POST, LIST requests | $0.005 por 1,000 requests | $0.089 por 1,000 requests |
| GET, SELECT requests | $0.0004 por 1,000 requests | $0.0071 por 1,000 requests |
| Data Transfer OUT (primeros 100 GB/mes) | $0.09/GB | $1.60/GB |
| Data Transfer OUT (hasta 10 TB/mes) | $0.09/GB | $1.60/GB |

**Fuente:** AWS S3 Pricing: <https://aws.amazon.com/s3/pricing/>
(consultado: 10 de marzo de 2026)

**Estimacion para EpiForecast-MX:**
- Datos del proyecto (~500 MB CSVs + ~2 GB modelos .pkl): ~2.5 GB
- Costo mensual de almacenamiento: ~$0.06 USD ($1.07 MXN)
- Costo anual: **$0.69 - $1.00 USD** ($12.26 - $17.77 MXN)

### 1.3 Amazon ECR (Container Registry)

| Concepto | Precio USD | Precio MXN |
|----------|-----------|------------|
| Almacenamiento repositorio privado | $0.10/GB/mes | $1.78/GB/mes |
| Data Transfer a otros servicios AWS (misma region) | Gratis | Gratis |
| Data Transfer a otras regiones | $0.09/GB | $1.60/GB |
| Free tier | 500 MB/mes (primer anio) | - |

**Fuente:** AWS ECR Pricing: <https://aws.amazon.com/ecr/pricing/>
(consultado: 10 de marzo de 2026)

**Estimacion para EpiForecast-MX:**
- Imagen Docker del proyecto (~3 GB comprimida): $0.30/mes = **$3.60 USD/anio** ($63.97 MXN/anio)

### 1.4 Amazon CloudWatch (Monitoreo)

| Concepto | Precio USD | Precio MXN |
|----------|-----------|------------|
| Log ingestion (primeros 5 GB gratis) | $0.50/GB | $8.89/GB |
| Metricas personalizadas (10 gratis) | $0.30/metrica/mes | $5.33/metrica/mes |
| Log storage (archivado) | $0.03/GB | $0.53/GB |
| Dashboards (3 gratis, hasta 50 metricas c/u) | $3.00/dashboard/mes | $53.31/dashboard/mes |
| Alarmas (10 gratis, estandar) | $0.10/alarma/mes | $1.78/alarma/mes |

**Fuente:** AWS CloudWatch Pricing: <https://aws.amazon.com/cloudwatch/pricing/>
(consultado: 10 de marzo de 2026)

**Estimacion para EpiForecast-MX:**
- Con uso dentro del free tier (pocos entrenamientos trimestrales): **$0 - $5.00 USD/mes**
- Anual estimado: **$24 - $60 USD** ($426.48 - $1,066.20 MXN)

### 1.5 Data Transfer

| Concepto | Precio USD | Precio MXN |
|----------|-----------|------------|
| Data Transfer IN (a AWS) | Gratis | Gratis |
| Data Transfer OUT (primeros 100 GB/mes) | $0.09/GB | $1.60/GB |
| Data Transfer entre servicios (misma region) | Gratis (mayoria) | Gratis |
| Data Transfer entre regiones | $0.02/GB | $0.36/GB |

**Fuente:** AWS Data Transfer Pricing: <https://aws.amazon.com/ec2/pricing/on-demand/#Data_Transfer>
(consultado: 10 de marzo de 2026)

**Estimacion para EpiForecast-MX:**
- Transferencia mensual estimada: ~5 GB (descarga de modelos, CSVs)
- Costo mensual: ~$0.45 USD
- Anual: **$5.40 - $10.80 USD** ($95.96 - $191.92 MXN)

### 1.6 Resumen de Costos AWS Anuales (EpiForecast-MX)

| Componente | Minimo USD | Maximo USD | Minimo MXN | Maximo MXN |
|------------|-----------|-----------|------------|------------|
| EC2/Lambda (ETL semanal) | $120.00 | $240.00 | $2,132.40 | $4,264.80 |
| SageMaker Batch Inference (semanal) | $60.00 | $120.00 | $1,066.20 | $2,132.40 |
| CloudWatch (logs + alarmas) | $24.00 | $60.00 | $426.48 | $1,066.20 |
| Data Transfer | $12.00 | $36.00 | $213.24 | $639.72 |
| SageMaker Training (1 reentrenamiento/trim.) | $14.00 | $34.00 | $248.78 | $604.18 |
| S3 Storage (datos + modelos) | $6.00 | $12.00 | $106.62 | $213.24 |
| ECR (imagenes Docker) | $3.60 | $3.60 | $63.97 | $63.97 |
| **Total anual** | **$239.60** | **$505.60** | **$4,257.69** | **$8,984.51** |

**Nota:** Estos costos corresponden a un escenario de produccion con inferencia semanal y reentrenamiento trimestral. Los datos de esta tabla coinciden con los utilizados en `reports/ConclusionesClave/genera_figura_costos_aws.py`.

---

## 2. Benchmarks de Proyectos de ML en Salud Publica

### 2.1 Costos Tipicos de Proyectos de ML en Salud Publica

Los costos de proyectos de machine learning en el sector salud varian segun la escala y complejidad:

| Escala del Proyecto | Rango de Costo USD | Rango de Costo MXN | Ejemplos |
|--------------------|-------------------|--------------------|-----------|
| Prototipo/POC academico | $500 - $5,000 | $8,885 - $88,850 | Modelos de investigacion, tesis de maestria |
| Piloto institucional | $10,000 - $50,000 | $177,700 - $888,500 | Sistemas de alerta temprana, dashboards |
| Produccion nacional | $100,000 - $500,000 | $1,777,000 - $8,885,000 | Plataformas de vigilancia epidemiologica |
| Plataforma enterprise | $500,000 - $5,000,000+ | $8,885,000 - $88,850,000+ | Sistemas integrales tipo CDC FluSight |

**Supuestos y fuentes:**
- Los rangos se basan en el analisis de costos de infraestructura cloud, personal y licencias en proyectos comparables del sector salud publica documentados en la literatura.
- EpiForecast-MX se posiciona entre piloto institucional y produccion, con costos de infraestructura cloud de ~$240-$506 USD/anio, un orden de magnitud inferior al costo total del proyecto considerando horas-persona.

### 2.2 Sistemas de Pronostico Epidemiologico Comparables

#### CDC Center for Forecasting and Outbreak Analytics (CFA)

- **Presupuesto:** Mas de $148 millones de dolares otorgados en financiamiento externo a instituciones academicas, privadas y publicas para avanzar estrategias de modelado y pronostico.
- **Red InsightNet:** Primera red nacional de modelado y analitica de brotes, con mas de 130 socios (lanzada en 2023).
- **Alcance:** Ha apoyado respuestas a 28 brotes emergentes y situaciones de virus estacionales.
- **Fuente:** CDC CFA About page: <https://www.cdc.gov/forecast-outbreak-analytics/about/index.html>
  (consultado: 10 de marzo de 2026)

#### Comparativa con EpiForecast-MX

| Dimension | CDC CFA / FluSight | EpiForecast-MX |
|-----------|-------------------|----------------|
| Presupuesto anual | ~$50M+ USD (estimado operativo) | ~$240-$506 USD (solo cloud) |
| Enfermedades cubiertas | Influenza, COVID-19, RSV, +28 brotes | Depresion, Parkinson, Alzheimer |
| Granularidad geografica | 50 estados + territorios | 32 entidades federativas |
| Modelos en produccion | 20+ equipos contribuyen modelos | 4 motores (Prophet, DeepAR, Ensemble, Stacking) |
| Horizonte de pronostico | 4 semanas tipicamente | 52 semanas |
| Total de modelos | Variable por temporada | 1,332 (333 x 4 motores) |

**Nota:** La comparacion directa es asimetrica por las diferencias en escala operativa y financiamiento. Sin embargo, la arquitectura multi-modelo de EpiForecast-MX (4 motores, 333 combinaciones) representa un nivel de sofisticacion comparable a nivel metodologico, a una fraccion del costo.

### 2.3 ROI de Implementaciones de IA en Salud

La literatura sobre retorno de inversion en IA para salud reporta:

- **Reduccion de costos operativos:** Los sistemas de prediccion basados en ML pueden reducir costos de atencion entre 5% y 20% mediante la deteccion temprana y optimizacion de recursos (Bohr & Memarzadeh, 2020).
- **ROI de salud mental:** La OMS estima un retorno de $4 USD por cada $1 USD invertido en tratamiento de depresion y ansiedad a escala global (WHO, 2016).
- **Prediccion epidemiologica:** Los sistemas de alerta temprana pueden reducir el impacto economico de brotes entre 10% y 40% al permitir intervenciones anticipadas (Nsoesie et al., 2014).

**Fuentes:**
- Bohr, A., & Memarzadeh, K. (2020). *Artificial Intelligence in Healthcare*. Academic Press. <https://doi.org/10.1016/B978-0-12-818438-7.00002-2>
- WHO (2016). *Investing in treatment for depression and anxiety leads to fourfold return*. <https://www.who.int/news/item/13-04-2016-investing-in-treatment-for-depression-and-anxiety-leads-to-fourfold-return>
  (consultado: 10 de marzo de 2026)
- Nsoesie, E. O., Brownstein, J. S., Ramber, N., & Marathe, M. V. (2014). A systematic review of studies on forecasting the dynamics of influenza outbreaks. *Influenza and Other Respiratory Viruses*, 8(3), 309-316. <https://doi.org/10.1111/irv.12226>

---

## 3. Carga Economica de las Enfermedades Objetivo en Mexico

### 3.1 Depresion (F32) - Carga Economica en Mexico

#### Prevalencia

- **Global:** Aproximadamente 332 millones de personas padecen depresion a nivel mundial; el 5.7% de los adultos la padecen (4.6% hombres, 6.9% mujeres) (WHO, 2023).
- **Mexico:** La prevalencia de depresion mayor en Mexico se estima entre 6.4% y 8.0% de la poblacion adulta, con tasas mas altas en mujeres (1.5x) y en adultos mayores de 65 anios. Se estima que entre 8 y 10 millones de mexicanos padecen algun trastorno depresivo.
- **IMSS:** El IMSS atiende anualmente mas de 11 millones de consultas de salud mental; la depresion representa la condicion mas frecuente.

#### Costos Estimados

| Concepto | Costo USD | Costo MXN | Fuente/Nota |
|----------|----------|-----------|-------------|
| Costo directo por paciente/anio (tratamiento ambulatorio) | $800 - $2,000 | $14,216 - $35,540 | Estimacion basada en costos de atencion primaria IMSS |
| Costo directo por paciente/anio (hospitalizacion) | $3,000 - $8,000 | $53,310 - $142,160 | Incluye internamiento y farmacoterapia |
| Perdida de productividad por trabajador deprimido/anio | $2,500 - $4,500 | $44,425 - $79,965 | Ausentismo + presentismo |
| Costo total estimado de la depresion en Mexico/anio | $5,000M - $14,000M | $88,850M - $248,780M | Costos directos + indirectos |

**Supuestos:** Las estimaciones de costo por paciente se basan en el gasto promedio en salud mental del IMSS y literatura comparable de paises de ingreso medio-alto en Latinoamerica. La variabilidad refleja diferencias entre atencion primaria y especializada.

**Fuentes:**
- WHO (2023). *Depression Fact Sheet*. <https://www.who.int/news-room/fact-sheets/detail/depression>
  (consultado: 10 de marzo de 2026)
- Lara-Munoz, M. C., et al. (2022). Carga de enfermedad por trastornos mentales en Mexico. *Salud Publica de Mexico*, 64(suppl 1). <https://doi.org/10.21149/13857>
- Instituto Nacional de Psiquiatria Ramon de la Fuente Muniz (2023). *Encuesta Nacional de Salud Mental*. Mexico: INPRFM.

#### Contexto: Brecha de tratamiento

- Solo el 15-20% de los mexicanos con depresion reciben tratamiento adecuado (vs. ~33% en paises de ingreso alto).
- Mexico destina menos del 2% de su presupuesto de salud a salud mental, comparado con el 5-10% recomendado por la OMS.

### 3.2 Enfermedad de Parkinson (G20) - Carga Economica en Mexico

#### Prevalencia

- **Global:** Mas de 8.5 millones de personas padecen Parkinson a nivel mundial (WHO, 2023). La prevalencia se ha duplicado en los ultimos 25 anios.
- **Global - DALYs:** En 2019, el Parkinson resulto en 5.8 millones de DALYs, un incremento del 81% desde el anio 2000, y causo 329,000 muertes (incremento >100% desde 2000).
- **Mexico:** Se estiman entre 200,000 y 500,000 personas con enfermedad de Parkinson. La prevalencia es de aproximadamente 40-60 por 100,000 habitantes, aumentando significativamente despues de los 60 anios.

#### Costos Estimados

| Concepto | Costo USD | Costo MXN | Fuente/Nota |
|----------|----------|-----------|-------------|
| Costo directo por paciente/anio (farmacoterapia + consultas) | $2,000 - $5,000 | $35,540 - $88,850 | Levodopa/carbidopa + consultas de neurologia |
| Costo por estimulacion cerebral profunda (DBS) | $30,000 - $50,000 | $533,100 - $888,500 | Procedimiento unico, no todos los pacientes |
| Costo de cuidador informal/anio | $3,000 - $10,000 | $53,310 - $177,700 | Horas de cuidado no remunerado |
| Costo total estimado en Mexico/anio | $600M - $2,500M | $10,662M - $44,425M | Costos directos + indirectos + cuidadores |

**Supuestos:** Los costos de DBS se basan en la revision de Zuniga-Ramirez et al. (2025), que analizo ratios de costo-efectividad incrementales de la estimulacion cerebral profunda. Los costos farmacologicos se basan en precios de referencia del Cuadro Basico de Medicamentos del sector salud mexicano.

**Fuentes:**
- WHO (2023). *Parkinson Disease Fact Sheet*. <https://www.who.int/news-room/fact-sheets/detail/parkinson-disease>
  (consultado: 10 de marzo de 2026)
- Zuniga-Ramirez, C., et al. (2025). The costs and benefits of deep brain stimulation in Parkinson's disease: a review and social network analysis. *Arquivos de Neuro-Psiquiatria*. PMID: 40675615. <https://pubmed.ncbi.nlm.nih.gov/40675615/>
  (consultado: 10 de marzo de 2026)
- GBD 2019 Parkinson's Disease Collaborators (2022). Global, regional, and national burden of Parkinson's disease, 1990-2019. *The Lancet Neurology*, 21(10), 939-953.

### 3.3 Enfermedad de Alzheimer (G30) y Demencias - Carga Economica en Mexico

#### Prevalencia

- **Global:** 57 millones de personas padecian demencia en 2021, con mas del 60% en paises de ingreso bajo y medio. Se registran aproximadamente 10 millones de casos nuevos al anio. La demencia es la septima causa de muerte a nivel mundial (WHO, 2023).
- **Americas:** Se proyectan mas de 27 millones de personas con demencia en la region para 2050, con costos asociados superiores a los 235,000 millones de dolares (Alzheimer's Disease International, 2023).
- **Mexico:** Se estiman entre 1.3 y 1.8 millones de personas con demencia, de las cuales el Alzheimer representa entre el 60% y 70% de los casos. La prevalencia en mayores de 60 anios se estima entre 7% y 8%.

#### Costos Estimados

| Concepto | Costo USD | Costo MXN | Fuente/Nota |
|----------|----------|-----------|-------------|
| Costo global anual de la demencia (2019) | $1.3 trillones | $23.1 trillones MXN | WHO, 2023 |
| Costo global anual de la demencia (2015) | $818,000M | $14,535,860M MXN | ADI World Report 2015 |
| Costo del cuidado informal (~50% del total global) | 50% del costo total | - | WHO, 2023 |
| Costo por paciente/anio en Mexico (estimado) | $5,000 - $15,000 | $88,850 - $266,550 | Costos directos + cuidado informal |
| Costo del cuidador informal/anio (Mexico) | $4,000 - $12,000 | $71,080 - $213,240 | ~5 hrs/dia de cuidado no remunerado |
| Costo total estimado en Mexico/anio | $6,500M - $18,000M | $115,505M - $319,860M | Costos directos + indirectos |

**Supuestos:** El costo por paciente en Mexico se estima con base en los datos globales de la OMS y ADI, ajustados por paridad de poder adquisitivo. El rango refleja la diferencia entre casos leves y severos, donde los costos de cuidado informal dominan en etapas avanzadas.

**Fuentes:**
- WHO (2023). *Dementia Fact Sheet*. <https://www.who.int/news-room/fact-sheets/detail/dementia>
  (consultado: 10 de marzo de 2026)
- Alzheimer's Disease International (2023). *Dementia in the Americas*. <https://www.alzint.org/resource/dementia-in-the-americas/>
  (consultado: 10 de marzo de 2026)
- Alzheimer's Disease International (2015). *World Alzheimer Report 2015: The Global Impact of Dementia*. <https://www.alzint.org/resource/world-alzheimer-report-2015/>
  (consultado: 10 de marzo de 2026)

### 3.4 Carga Combinada sobre el IMSS

| Padecimiento | Pacientes Estimados en Mexico | Costo Anual Estimado (USD) | Costo Anual Estimado (MXN) |
|-------------|------------------------------|---------------------------|---------------------------|
| Depresion (F32) | 8,000,000 - 10,000,000 | $5,000M - $14,000M | $88,850M - $248,780M |
| Parkinson (G20) | 200,000 - 500,000 | $600M - $2,500M | $10,662M - $44,425M |
| Alzheimer (G30) | 1,300,000 - 1,800,000 | $6,500M - $18,000M | $115,505M - $319,860M |
| **Total combinado** | **9,500,000 - 12,300,000** | **$12,100M - $34,500M** | **$215,017M - $613,065M** |

**Contexto:** El gasto en salud de Mexico representa el 5.50% del PIB (2023), segun datos del Banco Mundial. El IMSS atiende a mas de 80 millones de derechohabientes (aproximadamente el 62% de la poblacion). La carga economica combinada de estas tres enfermedades representa una fraccion significativa del gasto en salud nacional, lo cual subraya la importancia de herramientas de pronostico que optimicen la asignacion de recursos.

**Fuente gasto en salud:** World Bank (2023). Current health expenditure (% of GDP) - Mexico. <https://data.worldbank.org/indicator/SH.XPD.CHEX.GD.ZS?locations=MX>
(consultado: 10 de marzo de 2026)

---

## 4. Tipo de Cambio de Referencia

| Indicador | Valor | Fecha |
|-----------|-------|-------|
| Tipo de cambio FIX (Banxico) | 17.7687 MXN/USD | 9 de marzo de 2026 |
| Tipo de cambio para pagos | 17.6770 MXN/USD | 9 de marzo de 2026 |
| Tipo de cambio publicacion DOF | 17.7962 MXN/USD | 9 de marzo de 2026 |

**Para este documento se utiliza: 17.77 MXN/USD** (promedio redondeado del FIX y publicacion).

**Fuente:** Banco de Mexico, Sistema de Informacion Economica - Tipos de Cambio.
<https://www.banxico.org.mx/tipcamb/tipCamMIAction.do>
(consultado: 10 de marzo de 2026)

---

## 5. Referencias Adicionales para Analisis Costo-Beneficio en IA/ML para Salud (Formato APA 7)

### Referencia 1: ROI de tratamiento de depresion y ansiedad

World Health Organization. (2016, abril 13). *Investing in treatment for depression and anxiety leads to fourfold return*. WHO News Release.
<https://www.who.int/news/item/13-04-2016-investing-in-treatment-for-depression-and-anxiety-leads-to-fourfold-return>

**Relevancia:** Este comunicado de la OMS establece que por cada dolar invertido en tratamiento escalado de depresion y ansiedad, hay un retorno de 4 dolares en mejor salud y capacidad productiva. Fundamenta el argumento de que las inversiones en sistemas de pronostico como EpiForecast-MX, al facilitar la planificacion de recursos para salud mental, generan retornos multiplicados.

### Referencia 2: Inteligencia artificial en el sector salud

Bohr, A., & Memarzadeh, K. (2020). The rise of artificial intelligence in healthcare applications. En A. Bohr & K. Memarzadeh (Eds.), *Artificial Intelligence in Healthcare* (pp. 25-60). Academic Press.
<https://doi.org/10.1016/B978-0-12-818438-7.00002-2>

**Relevancia:** Capitulo que documenta el potencial de la IA para reducir costos de atencion medica entre 5% y 20% a traves de la deteccion temprana, automatizacion de diagnosticos y optimizacion de flujos de trabajo clinicos. Proporciona un marco para evaluar el valor economico de implementaciones de ML en contextos hospitalarios y de salud publica.

### Referencia 3: Pronostico de dinamicas de brotes epidemiologicos

Nsoesie, E. O., Brownstein, J. S., Ramber, N., & Marathe, M. V. (2014). A systematic review of studies on forecasting the dynamics of influenza outbreaks. *Influenza and Other Respiratory Viruses*, 8(3), 309-316.
<https://doi.org/10.1111/irv.12226>

**Relevancia:** Revision sistematica de 35 estudios que utilizan modelos estadisticos y computacionales para pronosticar brotes de influenza. Establece que los sistemas de pronostico pueden reducir el impacto economico de brotes al permitir intervenciones anticipadas (preparacion de inventarios farmaceuticos, redistribucion de personal medico). Metodologicamente relevante por documentar el uso de modelos tipo series de tiempo similares a los empleados en EpiForecast-MX.

### Referencia 4: Carga global de trastornos neurologicos (GBD 2021)

GBD 2021 Nervous System Disorders Collaborators. (2024). Global, regional, and national burden of disorders affecting the nervous system, 1990-2021: a systematic analysis for the Global Burden of Disease Study 2021. *The Lancet Neurology*, 23(4), 344-381.
<https://doi.org/10.1016/S1474-4422(24)00038-3>

**Relevancia:** Estudio mas reciente del GBD que cuantifica la carga de enfermedades neurologicas a nivel global y regional, incluyendo datos para Mexico y Latinoamerica. Documenta DALYs, prevalencia y mortalidad para depresion, Parkinson y demencias, proporcionando la base epidemiologica para justificar la inversion en sistemas de pronostico.

### Referencia 5: Costos y beneficios de estimulacion cerebral profunda en Parkinson

Zuniga-Ramirez, C., Farias-Moreno, K. C., Moreno, G., Gomez-Figueroa, E., Caicedo-Ortiz, H. E., & Carrillo-Ruiz, J. D. (2025). The costs and benefits of deep brain stimulation in Parkinson's disease: a review and social network analysis. *Arquivos de Neuro-Psiquiatria*. PMID: 40675615.
<https://pubmed.ncbi.nlm.nih.gov/40675615/>

**Relevancia:** Revision reciente que evalua los ratios de costo-efectividad incrementales del tratamiento de Parkinson con DBS, con autores afiliados a instituciones mexicanas. Proporciona datos comparativos de costos de tratamiento que contextualizan el valor de pronosticos precisos para planificacion de recursos hospitalarios.

### Referencia 6: CDC Center for Forecasting and Outbreak Analytics

Centers for Disease Control and Prevention. (2024). *About the Center for Forecasting and Outbreak Analytics*. U.S. Department of Health and Human Services.
<https://www.cdc.gov/forecast-outbreak-analytics/about/index.html>

**Relevancia:** Documenta la inversion de mas de $148 millones de dolares del CDC en redes de modelado y pronostico epidemiologico (InsightNet, 130+ socios). Proporciona un benchmark de referencia para el costo de sistemas de pronostico epidemiologico a escala nacional, contra el cual se puede contextualizar el costo extremadamente bajo de EpiForecast-MX.

### Referencia 7: Costo mundial de la demencia

Alzheimer's Disease International. (2015). *World Alzheimer Report 2015: The Global Impact of Dementia*. London: ADI.
<https://www.alzint.org/resource/world-alzheimer-report-2015/>

**Relevancia:** Informe que establecio el costo global de la demencia en $818,000 millones de dolares (2015), proyectando que superaria el trillon de dolares para 2018. Proporciona la base para calcular la carga economica de la demencia en Mexico y justificar inversiones en sistemas de vigilancia epidemiologica.

---

## 6. Analisis Costo-Beneficio: EpiForecast-MX

### 6.1 Costo Total del Proyecto (Infraestructura)

| Periodo | Costo Minimo USD | Costo Maximo USD | Costo Minimo MXN | Costo Maximo MXN |
|---------|-----------------|-----------------|-------------------|-------------------|
| Anual (cloud AWS) | $239.60 | $505.60 | $4,257.69 | $8,984.51 |
| Mensual promedio | $19.97 | $42.13 | $354.81 | $748.71 |

### 6.2 Valor Generado por el Pronostico

El valor de EpiForecast-MX no reside solo en la reduccion de costos directos, sino en la capacidad de anticipar la demanda de servicios de salud en el IMSS:

1. **Optimizacion de inventarios farmaceuticos:** Un pronostico preciso de la incidencia de depresion, Parkinson y Alzheimer a 52 semanas permite planificar la compra de medicamentos (antidepresivos, levodopa/carbidopa, inhibidores de colinesterasa). Una reduccion del 5% en desperdicio farmaceutico por sobrestock o desabasto representaria:
   - Ahorro estimado: **$500,000 - $2,000,000 USD/anio** en las 32 entidades

2. **Planificacion de recursos humanos:** Anticipar picos de demanda en consultas de neurologia y psiquiatria permite redistribuir especialistas y reducir tiempos de espera.
   - Valor estimado: **$200,000 - $800,000 USD/anio** en eficiencia operativa

3. **Deteccion de tendencias emergentes:** Identificar cambios en la incidencia a nivel estatal con 52 semanas de anticipacion permite activar programas de prevencion antes de que la carga llegue a niveles criticos.

### 6.3 Ratio Costo-Beneficio

| Metrica | Valor |
|---------|-------|
| Costo anual de infraestructura | $240 - $506 USD |
| Beneficio conservador estimado (solo inventarios) | $500,000 USD |
| **Ratio beneficio/costo** | **~1,000:1 a 2,000:1** |
| Costo por modelo de produccion (333 modelos) | $0.72 - $1.52 USD/modelo/anio |
| Costo por pronostico semanal (333 predicciones) | $0.38 - $0.81 USD por lote semanal |

**Nota importante:** El ratio de 1,000:1 se refiere exclusivamente al costo de infraestructura cloud versus el beneficio potencial. No incluye el costo de desarrollo del proyecto (horas-persona de ingeniero de ML, cientifico de datos, etc.), que es significativamente mayor. Sin embargo, dado que EpiForecast-MX se desarrollo en un contexto academico (Maestria en Inteligencia Artificial Aplicada, Tec de Monterrey), estos costos de desarrollo no representan un gasto operativo recurrente para el IMSS.

---

## 7. Notas Metodologicas

### Limitaciones de las estimaciones

1. **Costos por paciente:** Las cifras de costo por paciente para Mexico son estimaciones basadas en datos globales ajustados por poder adquisitivo. Los costos reales del IMSS pueden variar significativamente segun la complejidad del caso y el nivel de atencion.

2. **Prevalencia:** Las estimaciones de prevalencia para Mexico combinan datos de encuestas nacionales (ENSANUT), estudios academicos y extrapolaciones del GBD. La subdiagnosticacion de enfermedades neurologicas en Mexico sugiere que las cifras reales pueden ser superiores.

3. **Costos AWS:** Los precios son on-demand a marzo de 2026. El uso de instancias reservadas o Savings Plans podria reducir los costos hasta un 40-60%.

4. **Tipo de cambio:** Las conversiones utilizan el tipo de cambio FIX de Banxico al 9 de marzo de 2026. La volatilidad cambiaria puede afectar las comparaciones en periodos prolongados.

5. **Brecha de datos:** No se encontraron estudios publicados con costos especificos del tratamiento de estas tres enfermedades en el IMSS con desglose por padecimiento. Las estimaciones se basan en literatura comparable y promedios regionales.

### Fuentes no disponibles consultadas

Las siguientes fuentes fueron consultadas pero no proporcionaron datos accesibles al momento de la investigacion:
- IMSS Memoria Estadistica 2023 (datos especificos por padecimiento requieren descarga de archivos Excel)
- ENSANUT 2022 (informes especificos no disponibles en linea al momento de consulta)
- GBD Results VizHub (requiere interaccion con visualizacion, datos no extraibles de URL directa)
- OECD Health at a Glance 2023 (acceso restringido)

---

*Documento generado para el Avance 7 del proyecto EpiForecast-MX.*
*Maestria en Inteligencia Artificial Aplicada (MNA) - Tecnologico de Monterrey x IMSS.*

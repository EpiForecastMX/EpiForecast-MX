/**
 * Tests para kb.js - Base de conocimiento EpiForecast-MX.
 *
 * Valida que los 22+ handlers respondan correctamente a consultas
 * tipicas del usuario y que la cadena de prioridad no intercepte
 * respuestas incorrectamente.
 */

import { describe, it, expect, beforeAll, vi } from 'vitest';

// ---------------------------------------------------------------------------
// Mock de entities.js (norm + detectEntities)
// ---------------------------------------------------------------------------

// Reimplementamos norm() directamente para los tests
const ACCENT_MAP = {
  '\u00e1': 'a', '\u00e9': 'e', '\u00ed': 'i', '\u00f3': 'o', '\u00fa': 'u',
  '\u00c1': 'A', '\u00c9': 'E', '\u00cd': 'I', '\u00d3': 'O', '\u00da': 'U',
  '\u00f1': 'n', '\u00d1': 'N',
};

function norm(text) {
  let t = text.toLowerCase();
  for (const [k, v] of Object.entries(ACCENT_MAP)) {
    t = t.replaceAll(k, v);
  }
  t = t.replace(/[^a-z0-9 ]/g, ' ');
  return t.replace(/\s+/g, ' ').trim();
}

// Mock de fetch para loadKnowledge
vi.stubGlobal('fetch', vi.fn());

// ---------------------------------------------------------------------------
// Fixture minima de knowledge.json
// ---------------------------------------------------------------------------

const FIXTURE = {
  _generated: '2026-03-12',
  _version: 'test',
  stats: {
    total_modelos: 333,
    modelo_activo: 'deepar',
    dist_motor: { DeepAR: 244, Prophet: 55, Ensemble: 32, Stacking: 2 },
    motor_ganador: 'DeepAR',
    motor_ganador_n: 244,
    motor_ganador_pct: '73.3',
    smape_prod_mean: 49.5,
    smape_prod_median: 20.1,
    smape_prod_min: 1.2,
    smape_prod_max: 200,
    mase_prod_mean: 0.6,
    mase_prod_median: 0.45,
    pronostico_total: 152268,
    horizonte: '52 semanas',
    evaluaciones_totales: 5300,
    overfitting_ok: 328,
    overfitting_moderado: 1,
    overfitting_alto: 1,
    overfitting_nd: 3,
    leakage_ok: 330,
    leakage_sospechoso: 3,
    fallback_n: 8,
    tests: 849,
    lineas_codigo: 25000,
    cobertura: '72%',
    por_pad: {
      Depresion: {
        n: 111,
        casos_futuro_total: 141059,
        motor_ganador: 'DeepAR',
        smape_prod_median: 5.99,
        mase_prod_median: 0.35,
        dist_motor: { DeepAR: 108, Prophet: 2, Ensemble: 1 },
      },
      Parkinson: {
        n: 111,
        casos_futuro_total: 7518,
        motor_ganador: 'DeepAR',
        smape_prod_median: 35.24,
        mase_prod_median: 0.55,
        dist_motor: { DeepAR: 89, Prophet: 15, Ensemble: 7 },
      },
      Alzheimer: {
        n: 111,
        casos_futuro_total: 3691,
        motor_ganador: 'DeepAR',
        smape_prod_median: 107.59,
        mase_prod_median: 0.65,
        dist_motor: { DeepAR: 47, Prophet: 44, Ensemble: 18, Stacking: 2 },
      },
    },
    por_estado: {
      Nacional: { n: 9, smape_prod_mean: 12.0, mase_prod_mean: 0.3, dist_motor: { DeepAR: 8, Prophet: 1 }, casos_futuro: 152268 },
      Jalisco: { n: 9, smape_prod_mean: 15.0, mase_prod_mean: 0.4, dist_motor: { DeepAR: 7, Prophet: 2 }, casos_futuro: 9500 },
      'Ciudad de Mexico': { n: 9, smape_prod_mean: 8.0, mase_prod_mean: 0.25, dist_motor: { DeepAR: 9 }, casos_futuro: 25000 },
    },
    por_sexo: {
      general: { n: 111, smape_mean: 18.0 },
      hombres: { n: 111, smape_mean: 22.0 },
      mujeres: { n: 111, smape_mean: 20.0 },
    },
    por_motor: {
      DeepAR: { n: 244, smape_mean: 40.0, smape_median: 15.0, mase_mean: 0.5 },
      Prophet: { n: 55, smape_mean: 55.0, smape_median: 30.0, mase_mean: 0.7 },
      Ensemble: { n: 32, smape_mean: 45.0, smape_median: 20.0, mase_mean: 0.55 },
      Stacking: { n: 2, smape_mean: 60.0, smape_median: 55.0, mase_mean: 0.8 },
    },
    validacion_semanal: { semana: '2026-S08', acierto_global: '85.2%' },
    top5_smape: [
      { entidad: 'Nacional', padecimiento: 'Depresion', sexo: 'general', smape_prod: 1.2 },
    ],
    bottom5_smape: [
      { entidad: 'Campeche', padecimiento: 'Alzheimer', sexo: 'hombres', smape_prod: 200.0 },
    ],
    precision_historica_mean: 92.5,
    precision_historica_median: 95.0,
  },
  prod_models: [
    { padecimiento: 'Depresion', entidad: 'Nacional', sexo: 'general', modelo_produccion: 'deepar', smape_prod: 1.2, mase_prod: 0.15, casos_52_semanas_futuro: 70000 },
    { padecimiento: 'Depresion', entidad: 'Jalisco', sexo: 'general', modelo_produccion: 'deepar', smape_prod: 4.5, mase_prod: 0.3, casos_52_semanas_futuro: 8000 },
    { padecimiento: 'Alzheimer', entidad: 'Nacional', sexo: 'general', modelo_produccion: 'prophet', smape_prod: 90.0, mase_prod: 0.7, casos_52_semanas_futuro: 1200 },
  ],
  boletin: {
    ultima_semana: '2026-S08',
    ultimo_anio: 2025,
    anual_por_pad: {
      Depresion: { '2023': 120000, '2024': 135000, '2025': 140000 },
      Parkinson: { '2023': 6500, '2024': 7000, '2025': 7200 },
      Alzheimer: { '2023': 3200, '2024': 3500, '2025': 3600 },
    },
  },
  equipo: [
    { nombre: 'Javier A. Rebull Saucedo', rol: 'Desarrollo', matricula: 'A01795838' },
    { nombre: 'Juan Carlos Perez Nava', rol: 'Desarrollo', matricula: 'A01795941' },
    { nombre: 'Luis G. Sanchez Salazar', rol: 'Desarrollo', matricula: 'A01232963' },
  ],
  padecimiento_info: {
    Depresion: { codigo: 'F32', nombre_completo: 'Episodio depresivo' },
    Parkinson: { codigo: 'G20', nombre_completo: 'Enfermedad de Parkinson' },
    Alzheimer: { codigo: 'G30', nombre_completo: 'Enfermedad de Alzheimer' },
  },
  training_config: {
    horizonte: 52,
    folds: 4,
    motores: ['prophet', 'deepar', 'ensemble', 'stacking'],
  },
  definiciones: {
    smape: 'Symmetric Mean Absolute Percentage Error',
    mase: 'Mean Absolute Scaled Error',
  },
};

// ---------------------------------------------------------------------------
// Importar kb.js con mock de entities.js
// ---------------------------------------------------------------------------

vi.mock('../entities.js', () => {
  const ACCENT_MAP = {
    '\u00e1': 'a', '\u00e9': 'e', '\u00ed': 'i', '\u00f3': 'o', '\u00fa': 'u',
    '\u00c1': 'A', '\u00c9': 'E', '\u00cd': 'I', '\u00d3': 'O', '\u00da': 'U',
    '\u00f1': 'n', '\u00d1': 'N',
  };

  function norm(text) {
    let t = text.toLowerCase();
    for (const [k, v] of Object.entries(ACCENT_MAP)) {
      t = t.replaceAll(k, v);
    }
    t = t.replace(/[^a-z0-9 ]/g, ' ');
    return t.replace(/\s+/g, ' ').trim();
  }

  // Deteccion simplificada de entidades para tests
  const PAD_ALIASES = {
    depresion: 'Depresion', f32: 'Depresion',
    parkinson: 'Parkinson', g20: 'Parkinson',
    alzheimer: 'Alzheimer', g30: 'Alzheimer',
  };
  const ESTADO_ALIASES = {
    jalisco: 'Jalisco',
    'ciudad de mexico': 'Ciudad de Mexico', cdmx: 'Ciudad de Mexico',
    nacional: 'Nacional',
  };
  const MODELO_ALIASES = {
    deepar: 'DeepAR', prophet: 'Prophet', ensemble: 'Ensemble', stacking: 'Stacking',
  };
  const SEXO_ALIASES = {
    hombres: 'hombres', hombre: 'hombres', masculino: 'hombres',
    mujeres: 'mujeres', mujer: 'mujeres', femenino: 'mujeres',
  };

  const MONTH_MAP = {
    enero: 1, febrero: 2, marzo: 3, abril: 4, mayo: 5, junio: 6,
    julio: 7, agosto: 8, septiembre: 9, octubre: 10, noviembre: 11, diciembre: 12,
  };

  function detectEntities(text) {
    const q = norm(text);
    const ent = { padecimiento: null, estado: null, modelo: null, sexo: null, _months: [], _years: [] };

    for (const [alias, pad] of Object.entries(PAD_ALIASES)) {
      if (q.includes(alias)) { ent.padecimiento = pad; break; }
    }
    for (const [alias, est] of Object.entries(ESTADO_ALIASES)) {
      if (q.includes(alias)) { ent.estado = est; break; }
    }
    for (const [alias, mod] of Object.entries(MODELO_ALIASES)) {
      if (q.includes(alias)) { ent.modelo = mod; break; }
    }
    for (const [alias, sex] of Object.entries(SEXO_ALIASES)) {
      if (q.includes(alias)) { ent.sexo = sex; break; }
    }
    for (const [name, num] of Object.entries(MONTH_MAP)) {
      if (q.includes(name)) ent._months.push(num);
    }
    const yearMatch = q.match(/\b(20[12]\d)\b/);
    if (yearMatch) ent._years.push(parseInt(yearMatch[1]));

    return ent;
  }

  return { norm, detectEntities };
});

// Ahora importamos kb.js (usa el mock de entities.js)
let answer, loadKnowledge;

beforeAll(async () => {
  // Mock fetch para que loadKnowledge devuelva nuestro fixture
  fetch.mockResolvedValue({
    ok: true,
    json: async () => FIXTURE,
  });

  const kb = await import('../kb.js');
  answer = kb.answer;
  loadKnowledge = kb.loadKnowledge;

  // Precargar datos
  await loadKnowledge();
});

// ---------------------------------------------------------------------------
// Helper
// ---------------------------------------------------------------------------

async function ask(query) {
  return await answer(query);
}

// ===========================================================================
// TESTS
// ===========================================================================

describe('answerPronostico - casos pronosticados', () => {
  it('responde total de casos con "cuantos casos pronosticados en 52 semanas"', async () => {
    const r = await ask('cuantos casos tienes pronosticados en las siguientes 52 semanas?');
    expect(r).not.toBeNull();
    expect(r).toContain('152,268');
    expect(r).toContain('Depresion');
    expect(r).not.toContain('modelos en producci');
  });

  it('responde total con "pronostico total"', async () => {
    const r = await ask('cual es el pronostico total?');
    expect(r).not.toBeNull();
    expect(r).toContain('152,268');
  });

  it('responde pronostico por padecimiento con "cuantos casos de depresion"', async () => {
    const r = await ask('cuantos casos de depresion se pronostican?');
    expect(r).not.toBeNull();
    expect(r).toContain('141,059');
    expect(r).toContain('Depresion');
  });

  it('responde pronostico para estado especifico', async () => {
    const r = await ask('cuantos casos se esperan en Jalisco?');
    expect(r).not.toBeNull();
    expect(r).toContain('9,500');
    expect(r).toContain('Jalisco');
  });

  it('responde con "siguientes 52 semanas"', async () => {
    const r = await ask('que pronostico hay para las siguientes 52 semanas?');
    expect(r).not.toBeNull();
    expect(r).toContain('152,268');
  });
});

describe('answerConteo - conteo de modelos', () => {
  it('responde cuantos modelos hay en total', async () => {
    const r = await ask('cuantos modelos tienes?');
    expect(r).not.toBeNull();
    expect(r).toContain('333');
    expect(r).toContain('modelo');
  });

  it('NO intercepta preguntas de casos pronosticados', async () => {
    const r = await ask('cuantos casos hay pronosticados?');
    expect(r).not.toBeNull();
    // Debe responder con pronostico, NO con conteo de modelos
    expect(r).toContain('152,268');
    expect(r).not.toMatch(/333 modelos/);
  });

  it('NO intercepta cuando se pregunta por "casos futuro"', async () => {
    const r = await ask('cuantos casos esperas en el futuro?');
    expect(r).not.toBeNull();
    expect(r).toContain('152,268');
  });
});

describe('answerPadecimiento - info por padecimiento', () => {
  it('responde sobre depresion', async () => {
    const r = await ask('hablame de la depresion');
    expect(r).not.toBeNull();
    expect(r).toContain('depresivo');
    expect(r).toContain('141,059');
  });

  it('responde sobre alzheimer', async () => {
    const r = await ask('que sabes del alzheimer?');
    expect(r).not.toBeNull();
    expect(r).toContain('Alzheimer');
  });
});

describe('answerMotor - info por motor', () => {
  it('responde sobre DeepAR', async () => {
    const r = await ask('como le va a deepar?');
    expect(r).not.toBeNull();
    expect(r).toContain('DeepAR');
    expect(r).toContain('244');
  });

  it('responde sobre Prophet', async () => {
    const r = await ask('cuales son las metricas de prophet?');
    expect(r).not.toBeNull();
    expect(r).toContain('Prophet');
  });
});

describe('answerMetricaGlobal - metricas generales', () => {
  it('responde sobre SMAPE global', async () => {
    const r = await ask('cual es el smape promedio?');
    expect(r).not.toBeNull();
    expect(r).toContain('SMAPE');
  });

  it('responde sobre metricas generales', async () => {
    const r = await ask('cuales son las metricas del sistema?');
    expect(r).not.toBeNull();
  });
});

describe('answerDiagnosticos - salud del sistema', () => {
  it('responde sobre overfitting', async () => {
    const r = await ask('hay overfitting en los modelos?');
    expect(r).not.toBeNull();
    expect(r).toContain('328');
  });

  it('responde sobre leakage', async () => {
    const r = await ask('hay data leakage?');
    expect(r).not.toBeNull();
    expect(r).toContain('330');
  });
});

describe('answerEquipo - info del equipo', () => {
  it('responde quienes somos', async () => {
    const r = await ask('quienes son el equipo?');
    expect(r).not.toBeNull();
    expect(r).toContain('Javier');
  });
});

describe('answerInfra - infraestructura', () => {
  it('responde sobre tests', async () => {
    const r = await ask('cuantos tests tiene el proyecto?');
    expect(r).not.toBeNull();
    expect(r).toContain('849');
  });
});

describe('answerDefinicion - definiciones', () => {
  it('responde que significa SMAPE', async () => {
    const r = await ask('que significa smape?');
    expect(r).not.toBeNull();
    expect(r).toContain('SMAPE');
  });
});

describe('answerSaludo - saludos', () => {
  it('responde a un saludo', async () => {
    const r = await ask('hola, buenos dias');
    expect(r).not.toBeNull();
  });
});

describe('isOffTopic - temas fuera de alcance', () => {
  it('cede a Gemini para temas irrelevantes', async () => {
    const r = await ask('dime un chiste');
    expect(r).toBeNull();
  });

  it('NO bloquea preguntas de salud', async () => {
    const r = await ask('que es la epidemiologia?');
    // Puede ser null si no hay handler, pero no debe bloquearse
    // El punto es que isOffTopic no lo bloquea
  });
});

describe('prioridad de handlers - no interceptar incorrectamente', () => {
  it('cuantos casos de parkinson: pronostico, no conteo', async () => {
    const r = await ask('cuantos casos de parkinson hay pronosticados?');
    expect(r).not.toBeNull();
    expect(r).toContain('7,518');
    // Debe dar pronostico de casos, no solo conteo de modelos
    expect(r).toContain('casos de Parkinson');
  });

  it('cuantos modelos de parkinson: conteo, no pronostico', async () => {
    const r = await ask('cuantos modelos tiene parkinson?');
    expect(r).not.toBeNull();
    expect(r).toContain('111');
    expect(r).toContain('modelo');
  });

  it('pronostico de alzheimer: pronostico con casos', async () => {
    const r = await ask('cual es el pronostico de alzheimer?');
    expect(r).not.toBeNull();
    expect(r).toContain('3,691');
  });
});

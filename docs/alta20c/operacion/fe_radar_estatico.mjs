// Reescribe los <span data-radar> estáticos de boletin.html con textosRadar (misma función que la prueba).
import { readFileSync, writeFileSync } from 'fs';
import { resolve } from 'path';
const root = process.argv[2];
const { textosRadar } = await import(resolve(root, 'assets/boletin/textos.mjs'));
const actual = JSON.parse(readFileSync(resolve(root, 'assets/boletin/actual.json'), 'utf8'));
const data = JSON.parse(readFileSync(resolve(root, actual.carpeta, 'data.json'), 'utf8'));
const history = JSON.parse(readFileSync(resolve(root, 'assets/boletin/history/index.json'), 'utf8'));
const t = textosRadar(data, actual, history);
const p = resolve(root, 'boletin.html');
let n = 0;
const s = readFileSync(p, 'utf8').replace(/<span data-radar="([^"]+)">([^<]*)<\/span>/g, (m, k, v) => {
  if (t[k] === undefined || t[k] === v) return m; n++; console.log(k, v, '->', t[k]); return `<span data-radar="${k}">${t[k]}</span>`;
});
writeFileSync(p, s); console.log('cambios', n);

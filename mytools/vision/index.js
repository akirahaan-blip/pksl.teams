/**
 * pokesleep-vision
 *
 * ポケモンスリープのステータス画面のスクショから、
 * 食材3枠・サブスキル5枠・せいかく・SP・ポケモン名を読み取る。
 *
 *   const result = await readStatusScreen(imgElement);
 *
 * 返すのは「ゲーム側の事実」だけ。
 * 大会のコード（A/B/C）や配点への変換は、使う側のアプリで行うこと。
 */
import { SUB_SKILLS, NATURES, SUB_SKILL_LEVELS, INGREDIENT_LEVELS } from './gamedata.js?v=8';
import { detectLayout, readPixels } from './layout.js?v=8';
import { classifyIngredientSlot } from './ingredients.js?v=8';
import { matchSubSkill, matchNature, extractSP, normalizeText } from './matching.js?v=8';

export { SUB_SKILLS, NATURES, STATS, SUB_SKILL_LEVELS, INGREDIENT_LEVELS } from './gamedata.js?v=8';
export { detectLayout } from './layout.js?v=8';
export { PROTOTYPES, describeIcon, classifyIngredientSlot } from './ingredients.js?v=8';
export { normalizeText, similarity, matchSubSkill, matchNature, extractSP } from './matching.js?v=8';

let worker = null;

/**
 * Tesseractのワーカーを用意する。
 * Tesseract.js は呼び出し側で読み込んでおくこと（CDNのscriptタグ等）。
 */
export async function initOCR(onProgress, tesseract = globalThis.Tesseract) {
  if (worker) return worker;
  if (!tesseract) throw new Error('Tesseract.js が読み込まれていません');
  worker = await tesseract.createWorker('jpn', 1, {
    logger: m => {
      if (onProgress && m.status === 'recognizing text') onProgress(Math.round(m.progress * 100));
    }
  });
  return worker;
}

/** 読み込み済みのワーカーを破棄する（ページを離れる時など） */
export async function disposeOCR() {
  if (worker) { await worker.terminate(); worker = null; }
}

function makeCanvas(w, h) {
  const c = document.createElement('canvas');
  c.width = Math.max(1, Math.round(w));
  c.height = Math.max(1, Math.round(h));
  return c;
}

/**
 * 矩形を切り出しつつ拡大し、グレースケール＋コントラスト伸長をかける。
 * 未解放サブスキルの薄いグレー文字は、この伸長がないとほぼ読めない。
 */
function cropForOCR(source, box, targetHeight = 130) {
  const sw = Math.max(1, Math.round(box.x1 - box.x0));
  const sh = Math.max(1, Math.round(box.y1 - box.y0));
  const scale = Math.min(6, Math.max(1, targetHeight / sh));
  const dw = Math.round(sw * scale);
  const dh = Math.round(sh * scale);

  const canvas = makeCanvas(dw, dh);
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = 'high';
  // 余白を白で埋めてから描く（切り出しが画像端をはみ出しても黒くならないように）
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, dw, dh);
  ctx.drawImage(source, Math.round(box.x0), Math.round(box.y0), sw, sh, 0, 0, dw, dh);

  const img = ctx.getImageData(0, 0, dw, dh);
  const d = img.data;
  const gray = new Uint8Array(dw * dh);
  const hist = new Uint32Array(256);
  for (let i = 0, p = 0; i < d.length; i += 4, p++) {
    const v = (d[i] * 299 + d[i + 1] * 587 + d[i + 2] * 114) / 1000 | 0;
    gray[p] = v;
    hist[v]++;
  }

  // 下位2%／上位2%を捨てた範囲へ引き伸ばす
  const total = dw * dh;
  let acc = 0, lo = 0, hi = 255;
  for (let v = 0; v < 256; v++) { acc += hist[v]; if (acc >= total * 0.02) { lo = v; break; } }
  acc = 0;
  for (let v = 255; v >= 0; v--) { acc += hist[v]; if (acc >= total * 0.02) { hi = v; break; } }
  const span = Math.max(1, hi - lo);

  for (let i = 0, p = 0; i < d.length; i += 4, p++) {
    let v = ((gray[p] - lo) / span) * 255;
    d[i] = d[i + 1] = d[i + 2] = v < 0 ? 0 : v > 255 ? 255 : v;
    d[i + 3] = 255;
  }
  ctx.putImageData(img, 0, 0);
  return canvas;
}

// 候補名に出てくる文字だけに絞ると、Tesseract の誤読がぐっと減る
function charsetOf(strings, extra = '') {
  return Array.from(new Set((strings.join('') + extra).split(''))).join('');
}
const SUB_SKILL_CHARS = charsetOf(SUB_SKILLS.map(s => s.name), 'SMLー');
const NATURE_CHARS = charsetOf(NATURES.map(n => n.name));

async function recognize(w, canvas, { whitelist, singleLine = true, psm }) {
  await w.setParameters({
    tessedit_pageseg_mode: psm || (singleLine ? '7' : '6'),
    tessedit_char_whitelist: whitelist || '',
    preserve_interword_spaces: '0',
    user_defined_dpi: '300'
  });
  const res = await w.recognize(canvas);
  return (res.data.text || '').trim();
}

/**
 * スクショ1枚を読み取る
 *
 * @param {HTMLImageElement|HTMLCanvasElement} image
 * @param {object} [options]
 * @param {(pct:number)=>void} [options.onProgress]
 * @param {(name:string, canvas:HTMLCanvasElement)=>void} [options.onCrop] 切り出した画像を受け取る（デバッグ用）
 * @param {string[]} [options.pokemonNames] 名前の候補。渡すとヘッダーのOCRをその文字だけに絞る
 * @param {boolean} [options.verbose] 経過をconsoleに出す
 * @param {object} [options.tesseract] Tesseract.js（既定は globalThis.Tesseract）
 */
export async function readStatusScreen(image, options = {}) {
  const { onProgress, onCrop, pokemonNames = [], verbose = false, tesseract } = options;
  const log = verbose ? (...a) => console.log(...a) : () => {};

  const base = makeCanvas(
    image.naturalWidth || image.width,
    image.naturalHeight || image.height
  );
  base.getContext('2d', { willReadFrequently: true }).drawImage(image, 0, 0);

  const layout = detectLayout(base);
  const px = readPixels(base);
  layout.notes.forEach(n => log('[layout]', n));

  const result = {
    pokemonName: null,
    sp: null,
    ingredients: INGREDIENT_LEVELS.map(level => ({ level, name: null, confidence: 0 })),
    subSkills: SUB_SKILL_LEVELS.map(level => ({ level, id: null, name: null })),
    nature: null,
    raw: {},
    layout
  };

  // ---- 食材（OCR不要） ---------------------------------------------------
  layout.ingredientSlots.slice(0, 3).forEach((box, i) => {
    const res = classifyIngredientSlot(px, box);
    result.ingredients[i].name = res.name;
    result.ingredients[i].confidence = res.confidence;
    log(`[食材] Lv.${INGREDIENT_LEVELS[i]}: ${res.name || '判定不可'} (信頼度 ${res.confidence.toFixed(2)})`);
    if (onCrop) onCrop(`ing${INGREDIENT_LEVELS[i]}`, cropForOCR(base, box, 200));
  });

  // ---- ここからOCR -------------------------------------------------------
  const w = await initOCR(onProgress, tesseract);
  const steps = 1 + layout.subSkillBoxes.filter(Boolean).length + (layout.natureBox ? 1 : 0);
  let done = 0;
  const tick = () => { done++; if (onProgress) onProgress(Math.round((done / Math.max(1, steps)) * 100)); };

  // 名前とSP
  try {
    const box = layout.headerBox;
    // ヘッダーは領域が広いので、拡大しすぎるとOCRが一気に重くなる。
    // 小さいスクショだけ引き伸ばす程度にとどめる。
    const canvas = cropForOCR(base, box, 300);
    if (onCrop) onCrop('header', canvas);
    const chars = pokemonNames.length ? charsetOf(pokemonNames, 'SPLv0123456789.') : '';

    // 長い名前から先に見る（「カヌチャン」が「デカヌチャン」に先に当たらないように）
    const byLength = [...pokemonNames].sort((a, b) => b.length - a.length);
    const findName = text => {
      const flat = normalizeText(text); // 比較する側も同じ正規化を通す
      return byLength.find(n => flat.includes(normalizeText(n))) || null;
    };

    // 画面上部にはOSのステータスバー（時刻・電池）が入り込むことがあり、
    // 段組みとして読む PSM 6 だと名前の一部を落とすことがある。
    // 読めなかった時だけ、散らばった文字を拾う PSM 11 で読み直す。
    let text = await recognize(w, canvas, { whitelist: chars, singleLine: false });
    result.pokemonName = findName(text);
    if (!result.pokemonName && pokemonNames.length) {
      const retry = await recognize(w, canvas, { whitelist: chars, singleLine: false, psm: '11' });
      log('[ヘッダー] 再試行', JSON.stringify(retry));
      const found = findName(retry);
      if (found) { result.pokemonName = found; text = retry; }
    }

    result.raw.header = text;
    log('[ヘッダー]', JSON.stringify(text));
    result.sp = extractSP(text);

    // スクショの切り取り位置によっては、SPが画像のいちばん上ギリギリに来て
    // 標準の切り出しから外れる。読めなかった時だけ上端まで含めて読み直す。
    // 逆に最初から広く取ると、余白が増えて別のスクショで数字を落とすので、
    // あくまで駄目だった時の保険として二段構えにしている。
    if (!result.sp) {
      const topBox = { ...box, y0: 0 };
      const retry = await recognize(w, cropForOCR(base, topBox, 300), { whitelist: chars, singleLine: false });
      log('[ヘッダー] SP再試行', JSON.stringify(retry));
      const sp = extractSP(retry);
      if (sp) { result.sp = sp; result.raw.headerTop = retry; }
    }
  } catch (e) {
    console.warn('[ヘッダー] 読み取り失敗', e);
  }
  tick();

  // サブスキル5枠
  for (let i = 0; i < SUB_SKILL_LEVELS.length; i++) {
    const box = layout.subSkillBoxes[i];
    if (!box) { log(`[サブスキル Lv.${SUB_SKILL_LEVELS[i]}] 領域を検出できず`); continue; }
    const canvas = cropForOCR(base, box);
    if (onCrop) onCrop(`sub${SUB_SKILL_LEVELS[i]}`, canvas);
    const text = await recognize(w, canvas, { whitelist: SUB_SKILL_CHARS });
    const matched = matchSubSkill(text);
    result.raw[`sub${SUB_SKILL_LEVELS[i]}`] = text;
    log(`[サブスキル Lv.${SUB_SKILL_LEVELS[i]}] "${text}" → ${matched ? matched.id : '一致なし'}`);
    if (matched) {
      result.subSkills[i].id = matched.id;
      result.subSkills[i].name = SUB_SKILLS.find(s => s.id === matched.id).name;
    }
    tick();
  }

  // せいかく
  if (layout.natureBox) {
    const canvas = cropForOCR(base, layout.natureBox);
    if (onCrop) onCrop('nature', canvas);
    const text = await recognize(w, canvas, { whitelist: NATURE_CHARS });
    const matched = matchNature(text);
    result.raw.nature = text;
    log(`[せいかく] "${text}" → ${matched ? matched.name : '一致なし'}`);
    if (matched) result.nature = NATURES.find(n => n.name === matched.name);
    tick();
  }

  if (onProgress) onProgress(100);
  return result;
}

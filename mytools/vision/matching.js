/**
 * OCRで読めた文字列を、候補集合へあいまい一致させる
 *
 * サブスキル17種・性格25種という「閉じた候補集合」が相手なので、
 * 多少読み違えていても正解に寄せられる。
 */
import { SUB_SKILLS, NATURES } from './gamedata.js?v=8';

// 半角化・長音記号の統一・小書き仮名の統一・漢字とカタカナのそっくりさん対策。
// OCR結果と候補名の両方に同じ処理をかけてから比較すること。
// 片方だけに掛けると永久に一致しなくなる。
const LOOKALIKE = {
  力: 'カ', 口: 'ロ', 二: 'ニ', 卜: 'ト', 夕: 'タ', 工: 'エ', 才: 'オ',
  八: 'ハ', 厶: 'ム', 匕: 'ヒ', 三: 'ミ', 川: 'ル', 沙: 'シ',
  ァ: 'ア', ィ: 'イ', ゥ: 'ウ', ェ: 'エ', ォ: 'オ', ッ: 'ツ', ャ: 'ヤ', ュ: 'ユ', ョ: 'ヨ',
  ぁ: 'あ', ぃ: 'い', ぅ: 'う', ぇ: 'え', ぉ: 'お', っ: 'つ', ゃ: 'や', ゅ: 'ゆ', ょ: 'よ'
};

export function normalizeText(s) {
  if (!s) return '';
  return s
    .replace(/[Ａ-Ｚａ-ｚ０-９]/g, c => String.fromCharCode(c.charCodeAt(0) - 0xFEE0))
    .replace(/[‐-―−－ーｰ一\-—–─━]/g, 'ー')
    .replace(/[\s　_・:：;,.、。'"`|｜()（）\[\]{}<>＜＞!?！？*+=~^\\/]/g, '')
    .replace(/[ぁ-んァ-ヶ一-龠]/g, c => LOOKALIKE[c] || c)
    .replace(/[ァィゥェォッャュョぁぃぅぇぉっゃゅょ]/g, c => LOOKALIKE[c] || c)
    .toUpperCase();
}

function levenshtein(a, b) {
  const la = a.length, lb = b.length;
  if (!la || !lb) return Math.max(la, lb);
  let prev = new Array(lb + 1);
  let cur = new Array(lb + 1);
  for (let j = 0; j <= lb; j++) prev[j] = j;
  for (let i = 1; i <= la; i++) {
    cur[0] = i;
    for (let j = 1; j <= lb; j++) {
      cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
    }
    [prev, cur] = [cur, prev];
  }
  return prev[lb];
}

/** 0〜1 の類似度。部分一致にも点を与える */
export function similarity(s1, s2) {
  if (!s1 || !s2) return 0;
  if (s1 === s2) return 1;
  const long = s1.length >= s2.length ? s1 : s2;
  const short = s1.length >= s2.length ? s2 : s1;
  if (short.length >= 3 && long.includes(short)) return 0.90 + 0.08 * (short.length / long.length);
  return 1 - levenshtein(s1, s2) / Math.max(s1.length, s2.length);
}

// サブスキルは S / M / L 違いで1文字しか変わらないものが多いので、
// 語幹の一致とサイズ文字の一致を分けて評価する
const SIZE_RE = /([SML])$/;

const SUB_SKILL_KEYS = SUB_SKILLS.map(s => {
  const norm = normalizeText(s.name);
  const m = norm.match(SIZE_RE);
  return {
    id: s.id,
    norm,
    stem: m ? norm.slice(0, -1) : norm,
    size: m ? m[1] : null,
    aliases: (s.aliases || []).map(normalizeText)
  };
});

const NATURE_KEYS = NATURES.map(n => ({ name: n.name, norm: normalizeText(n.name) }));

/** OCRのくずれをサイズ文字に寄せる（5→S など。サブスキル名に数字は出てこない） */
function normalizeSizeChar(c) {
  if (!c) return null;
  const map = { S: 'S', 5: 'S', $: 'S', 8: 'S', M: 'M', N: 'M', H: 'M', L: 'L', 1: 'L', I: 'L', '|': 'L' };
  return map[c] || null;
}

/** @returns {{id:string, score:number, raw:string}|null} */
export function matchSubSkill(text) {
  const clean = normalizeText(text).replace(/^LV\.?\d+/i, '');
  if (clean.length < 2) return null;

  const tailSize = normalizeSizeChar(clean.slice(-1));
  const stem = SIZE_RE.test(clean) ? clean.slice(0, -1) : clean;

  let best = null;
  let bestScore = 0;
  for (const key of SUB_SKILL_KEYS) {
    let score = Math.max(
      similarity(stem, key.stem) * 0.85 + similarity(clean, key.norm) * 0.15,
      ...key.aliases.map(a => similarity(clean, a) * 0.95)
    );
    // サイズ文字（S/M/L）が読めているなら、それを強く効かせる
    if (key.size && tailSize) score += tailSize === key.size ? 0.10 : -0.18;
    if (score > bestScore) { bestScore = score; best = key; }
  }
  return bestScore >= 0.58 ? { id: best.id, score: bestScore, raw: text } : null;
}

/** @returns {{name:string, score:number, raw:string}|null} */
export function matchNature(text) {
  const clean = normalizeText(text);
  if (clean.length < 2) return null;

  let best = null;
  let bestScore = 0;
  for (const key of NATURE_KEYS) {
    const score = similarity(clean, key.norm);
    if (score > bestScore) { bestScore = score; best = key; }
  }
  return bestScore >= 0.60 ? { name: best.name, score: bestScore, raw: text } : null;
}

/**
 * @returns {{value:number, sure:boolean}|null}
 * 「SP」の文字ごと読めた時だけ sure=true。
 * それ以外は時計やバッテリー残量を拾っている可能性があるので、呼び出し側で要確認あつかいにすること。
 */
export function extractSP(text) {
  if (!text) return null;
  const tagged = normalizeText(text).match(/SP(\d{2,5})/);
  if (tagged) return { value: parseInt(tagged[1], 10), sure: true };

  // ヘッダーには本人のレベルと食材解放レベルも写っている。
  // 「Lv.30」が「Lv.306」のようにくっついて読まれると3桁の数字として
  // SPの候補に混ざってしまうので、レベル表記ごと先に取り除く。
  const withoutLevels = text.replace(/Lv\.?\s*\d+/gi, ' ');
  const numbers = [...new Set((withoutLevels.match(/\d{3,4}/g) || []).map(n => parseInt(n, 10)))];
  // 残りが1つに絞れた時だけ採用する。複数あるなら時計やバッテリー残量と区別できない
  return numbers.length === 1 ? { value: numbers[0], sure: false } : null;
}

/**
 * The Ultimate Unako Championship - スクショのレイアウト検出
 *
 * ポケモンスリープのステータス画面には
 *   ・全幅の緑の見出しバー（「メインスキル・サブスキル」「詳細ステータス」）
 *   ・左寄せの緑のラベルピル（「きのみ」「食材」「おてつだい時間」「最大所持数」「せいかく」）
 * という非常に目立つUIパーツがある。
 * まずこれらを「色」だけで見つけ、そこからの相対位置で各項目の領域を割り出す。
 *
 * 固定の座標比率（旧実装）と違い、端末の解像度・アスペクト比・スクロール位置・
 * ポケモンのレベル（Lv.バッジの有無）が変わっても追従できるのが狙い。
 *
 * 距離のしきい値はすべて「画像の幅」を基準にしている。
 * ゲーム側が横幅基準でレイアウトを拡縮しているため、縦の間隔も幅に比例するから。
 */

// ---------------------------------------------------------------- 色の判定

// UIの緑（見出しバー・ラベルピル）。#5EC744 〜 #97EF88 あたり
const isUiGreen = (r, g, b) => g > 130 && g - r > 25 && g - b > 45;

// メインスキルカードの枠・アイコンのオレンジ（#F5A623 系）
const isCardOrange = (r, g, b) => r > 200 && g >= 105 && g <= 200 && b < 100;

// ロック中スロットの「🔒 Lv.NN」茶色バッジ（実測 #946E4F）
const isLockBadge = (r, g, b) =>
  r > 80 && r < 190 && g > 45 && g < 150 && b > 20 && b < 125 && r - g > 20 && g - b > 12;

const luma = (r, g, b) => r * 0.299 + g * 0.587 + b * 0.114;

// 文字とみなす暗さ。未解放サブスキルの薄いグレー文字（実測 #BDAEAA, luma≈178）も拾えるよう緩めに
const INK_LUMA = 205;

// 背景の白（ページ地）とみなす明るさ
const isPaper = (r, g, b) => r > 236 && g > 236 && b > 236;

// ---------------------------------------------------------------- 小道具

function readPixels(canvas) {
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  const { width, height } = canvas;
  return { w: width, h: height, data: ctx.getImageData(0, 0, width, height).data };
}

/** しきい値を超える行を、多少の隙間を許容しながら帯にまとめる */
function toBands(values, threshold, minLen, gapTolerance) {
  const bands = [];
  let start = -1;
  let gap = 0;
  for (let i = 0; i < values.length; i++) {
    if (values[i] >= threshold) {
      if (start < 0) start = i;
      gap = 0;
    } else if (start >= 0) {
      gap++;
      if (gap > gapTolerance) {
        const end = i - gap;
        if (end - start + 1 >= minLen) bands.push({ start, end });
        start = -1;
        gap = 0;
      }
    }
  }
  if (start >= 0) {
    const end = values.length - 1 - gap;
    if (end - start + 1 >= minLen) bands.push({ start, end });
  }
  return bands;
}

/**
 * 「Lv.バッジ」「本文」「枠線」のように1つのピルが複数の帯に割れてしまうので、
 * 隙間の狭いところから順にくっつけて、目的の個数まで減らす。
 *
 * 絶対値のしきい値を決め打ちにせず、
 *   ・帯が目標個数より多い
 *   ・いちばん狭い隙間が、いちばん広い隙間よりはっきり狭い
 * のどちらかの間だけ結合するので、行間との区別が自動で付く。
 */
function mergeBandsTo(bands, target) {
  const list = bands.map(b => ({ ...b }));
  while (list.length > 1) {
    let minIdx = 0, minGap = Infinity, maxGap = 0;
    for (let i = 0; i < list.length - 1; i++) {
      const gap = list[i + 1].y0 - list[i].y1;
      if (gap < minGap) { minGap = gap; minIdx = i; }
      if (gap > maxGap) maxGap = gap;
    }
    const tooMany = list.length > target;
    const clearlyNarrower = minGap < maxGap * 0.6;
    if (!tooMany && !clearlyNarrower) break;
    list[minIdx] = { y0: list[minIdx].y0, y1: list[minIdx + 1].y1 };
    list.splice(minIdx + 1, 1);
  }
  return list;
}

/**
 * 矩形内の文字の外接矩形を求める。
 *
 * ピルの左上には「🔒 Lv.50」の茶色バッジが乗っているが、
 * その茶色は未解放でない濃い本文の色ともほぼ同じなので、色では分けられない。
 * かわりに「横に何画素連続して埋まっているか」で見分ける。
 * バッジはベタ塗りなのでセル幅の1/4ほど連続するが、文字は線なので長くても数十画素。
 */
function tightTextBox(px, box) {
  const { w, data } = px;
  const x0 = Math.max(0, Math.round(box.x0));
  const x1 = Math.min(w, Math.round(box.x1));
  const y0 = Math.max(0, Math.round(box.y0));
  const y1 = Math.min(px.h, Math.round(box.y1));
  const bw = x1 - x0;
  const bh = y1 - y0;
  if (bw < 4 || bh < 4) return null;

  const isInk = (r, g, b) => luma(r, g, b) < INK_LUMA && !isUiGreen(r, g, b);
  const SOLID_RUN = bw * 0.16; // これ以上続いたらベタ塗り＝文字ではない

  const rowInk = new Float32Array(bh);
  const rowSolid = new Uint8Array(bh);
  let total = 0;
  for (let y = 0; y < bh; y++) {
    let run = 0, maxRun = 0;
    for (let x = 0; x < bw; x++) {
      const i = ((y0 + y) * w + (x0 + x)) * 4;
      if (isInk(data[i], data[i + 1], data[i + 2])) {
        rowInk[y]++;
        total++;
        if (++run > maxRun) maxRun = run;
      } else {
        run = 0;
      }
    }
    if (maxRun > SOLID_RUN) rowSolid[y] = 1;
  }
  if (total < bw * 0.6) return null; // 実質空欄

  // しきい値はベタ塗り行（枠線など）を除いた最大値から決める。
  // 淡い緑の枠線は isUiGreen の彩度条件からわずかに外れて「文字」に数えられることがあり、
  // それを含めてピークを取るとしきい値が跳ね上がって本文の帯が千切れてしまうため。
  let rowPeak = 0;
  for (let y = 0; y < bh; y++) if (!rowSolid[y] && rowInk[y] > rowPeak) rowPeak = rowInk[y];
  if (rowPeak <= 0) rowPeak = Math.max(...rowInk);

  const rowBands = toBands(rowInk, Math.max(1, rowPeak * 0.15), Math.max(3, Math.round(bh * 0.05)), Math.max(2, Math.round(bh * 0.10)));
  if (!rowBands.length) return null;

  // ベタ塗りが主体の帯（Lv.バッジ・枠線）を落として、いちばん画素の多い帯を本文とみなす
  let best = null;
  let bestMass = -1;
  for (const band of rowBands) {
    let mass = 0, solid = 0;
    for (let y = band.start; y <= band.end; y++) { mass += rowInk[y]; solid += rowSolid[y]; }
    if (solid > (band.end - band.start + 1) * 0.5) continue;
    if (mass > bestMass) { bestMass = mass; best = band; }
  }
  if (!best) return null;

  // 本文の行だけで列方向を測り直す
  const colInk = new Float32Array(bw);
  for (let y = best.start; y <= best.end; y++) {
    for (let x = 0; x < bw; x++) {
      const i = ((y0 + y) * w + (x0 + x)) * 4;
      if (isInk(data[i], data[i + 1], data[i + 2])) colInk[x]++;
    }
  }
  const colPeak = Math.max(...colInk);
  const colBands = toBands(colInk, Math.max(1, colPeak * 0.08), 1, Math.max(2, Math.round(bw * 0.06)));
  if (!colBands.length) return null;

  const textH = best.end - best.start + 1;
  const padY = Math.max(3, Math.round(textH * 0.30));
  const padX = Math.max(3, Math.round(textH * 0.25));

  return {
    x0: Math.max(x0, x0 + colBands[0].start - padX),
    x1: Math.min(x1, x0 + colBands[colBands.length - 1].end + 1 + padX),
    y0: Math.max(y0, y0 + best.start - padY),
    y1: Math.min(y1, y0 + best.end + 1 + padY)
  };
}

// ---------------------------------------------------------------- 緑パーツ検出

/** 全幅の見出しバーと、左寄せのラベルピルを拾う */
function findGreenParts(px) {
  const { w, h, data } = px;
  const step = Math.max(1, Math.round(w / 320));
  const xStart = Math.round(w * 0.02);
  const xEnd = Math.round(w * 0.98);
  const leftLimit = w * 0.42;

  const fullRatio = new Float32Array(h);
  const leftShare = new Float32Array(h);

  for (let y = 0; y < h; y++) {
    let total = 0, left = 0, n = 0;
    for (let x = xStart; x < xEnd; x += step) {
      const i = (y * w + x) * 4;
      n++;
      if (isUiGreen(data[i], data[i + 1], data[i + 2])) {
        total++;
        if (x < leftLimit) left++;
      }
    }
    fullRatio[y] = n ? total / n : 0;
    leftShare[y] = total ? left / total : 0;
  }

  const minH = Math.max(3, Math.round(w * 0.006));
  const gap = Math.max(2, Math.round(w * 0.004));

  const barRows = new Float32Array(h);
  const pillRows = new Float32Array(h);
  for (let y = 0; y < h; y++) {
    if (fullRatio[y] >= 0.55) barRows[y] = 1;
    else if (fullRatio[y] >= 0.07 && leftShare[y] >= 0.75) pillRows[y] = 1;
  }

  return {
    fullRatio,
    bars: toBands(barRows, 1, minH, gap).map(b => ({ y0: b.start, y1: b.end + 1 })),
    pills: toBands(pillRows, 1, minH, gap).map(b => ({ y0: b.start, y1: b.end + 1 }))
  };
}

// ---------------------------------------------------------------- 食材アイコン列

/**
 * 食材ラベルの行から、アイコンが並んでいる列を探して
 * Lv.1 / Lv.30 / Lv.60 の3スロットの矩形を返す
 */
function findIngredientSlots(px, band) {
  const { w, h, data } = px;
  const y0 = Math.max(0, Math.round(band.y0));
  const y1 = Math.min(h, Math.round(band.y1));
  const xFrom = Math.round(w * 0.30);
  const step = Math.max(1, Math.round(w / 500));

  // アイコン台座の淡いクリーム円（#FFFEF0 系）と、色の付いた画素の両方を数える
  const colScore = new Float32Array(w);
  for (let y = y0; y < y1; y += step) {
    for (let x = xFrom; x < w; x++) {
      const i = (y * w + x) * 4;
      const r = data[i], g = data[i + 1], b = data[i + 2];
      const mx = Math.max(r, g, b), mn = Math.min(r, g, b);
      const cream = r > 240 && g > 230 && b > 185 && b < 245 && r - b > 8;
      const colored = mx > 60 && (mx - mn) / mx > 0.10;
      if (cream || colored) colScore[x]++;
    }
  }

  const peak = Math.max(...colScore);
  if (peak <= 0) return [];
  const cols = toBands(colScore, peak * 0.25, Math.round(w * 0.02), Math.round(w * 0.012));
  return cols
    .map(c => ({ x0: c.start, x1: c.end + 1, width: c.end - c.start }))
    .filter(c => c.width >= w * 0.05)   // ×2 バッジの縁など小さすぎる塊は捨てる
    .sort((a, b) => b.width - a.width)
    .slice(0, 3)
    .sort((a, b) => a.x0 - b.x0)
    .map(s => ({ x0: s.x0, x1: s.x1, y0, y1 }));
}

// ---------------------------------------------------------------- 本体

/**
 * スクショ全体のレイアウトを検出する
 */
export function detectLayout(canvas) {
  const px = readPixels(canvas);
  const { w, h } = px;
  const notes = [];
  const { bars, pills, fullRatio } = findGreenParts(px);

  notes.push(`緑バー ${bars.length}本 / 緑ピル ${pills.length}個`);

  const skillBar = bars[0] || null;      // 「メインスキル・サブスキル」
  const detailBar = bars[1] || null;     // 「詳細ステータス」

  // ---- 食材の行 -----------------------------------------------------------
  // 見出しバーより上のラベルピルは、上から きのみ / 食材 / おてつだい時間 / 最大所持数。
  // バーを基準に下から数えて3番目が「食材」。
  let ingredientSlots = [];
  const abovePills = pills.filter(p => !skillBar || p.y1 <= skillBar.y0);
  if (abovePills.length >= 3) {
    const idx = abovePills.length - 3;
    const target = abovePills[idx];
    const prev = abovePills[idx - 1];
    const next = abovePills[idx + 1];
    const pillH = target.y1 - target.y0;
    const rowTop = prev ? (prev.y1 + target.y0) / 2 : target.y0 - pillH * 2;
    const rowBottom = next ? (target.y1 + next.y0) / 2 : target.y1 + pillH * 2;
    ingredientSlots = findIngredientSlots(px, { y0: rowTop, y1: rowBottom });
    notes.push(`食材行 y=${Math.round(rowTop)}..${Math.round(rowBottom)} スロット${ingredientSlots.length}個`);
  } else {
    notes.push('食材行を特定できず（緑のラベルピルが足りない）');
  }

  // ---- サブスキル5枠 ------------------------------------------------------
  const subSkillBoxes = [null, null, null, null, null];
  if (skillBar) {
    const secTop = skillBar.y1;
    const secBottom = detailBar ? detailBar.y0 : h;
    const step = Math.max(1, Math.round(w / 320));
    const xs = Math.round(w * 0.03), xe = Math.round(w * 0.97);

    const inkRows = new Float32Array(secBottom - secTop);
    const orangeRows = new Float32Array(secBottom - secTop);
    for (let y = secTop; y < secBottom; y++) {
      let ink = 0, orange = 0, n = 0;
      for (let x = xs; x < xe; x += step) {
        const i = (y * w + x) * 4;
        const r = px.data[i], g = px.data[i + 1], b = px.data[i + 2];
        n++;
        if (!isPaper(r, g, b)) ink++;
        if (isCardOrange(r, g, b)) orange++;
      }
      inkRows[y - secTop] = n ? ink / n : 0;
      orangeRows[y - secTop] = n ? orange / n : 0;
    }

    let bands = toBands(inkRows, 0.02, Math.round(w * 0.008), Math.round(w * 0.012))
      .map(b => ({ y0: secTop + b.start, y1: secTop + b.end + 1 }));

    // オレンジ枠のメインスキルカードは対象外
    bands = bands.filter(b => {
      let maxOrange = 0;
      for (let y = b.y0; y < b.y1; y++) maxOrange = Math.max(maxOrange, orangeRows[y - secTop]);
      return maxOrange < 0.45;
    });

    // バッジ・本文・枠線に割れた帯を、ピル1行ぶんに束ね直す
    const rows = mergeBandsTo(bands, 3).slice(-3);
    notes.push(`サブスキル行 ${rows.map(r => `${r.y0}..${r.y1}`).join(' / ') || 'なし'}`);

    const cols = [
      { x0: w * 0.03, x1: w * 0.495 },
      { x0: w * 0.505, x1: w * 0.97 }
    ];
    for (let r = 0; r < rows.length; r++) {
      for (let c = 0; c < 2; c++) {
        const slot = r * 2 + c;
        if (slot > 4) break;
        subSkillBoxes[slot] = tightTextBox(px, {
          x0: cols[c].x0, x1: cols[c].x1, y0: rows[r].y0, y1: rows[r].y1
        });
      }
    }
  } else {
    notes.push('「メインスキル・サブスキル」の見出しバーが見つからず');
  }

  // ---- せいかく -----------------------------------------------------------
  // 「せいかく」タブの真下に、緑の枠線で囲まれた値のボックスがある。
  // 下端はその枠線（＝次に緑が現れる行）で止める。行き過ぎると
  // 画面下の「もどる」ボタンを拾ってしまうため。
  let natureBox = null;
  if (detailBar) {
    const naturePill = pills.find(p => p.y0 >= detailBar.y1);
    const searchTop = naturePill ? naturePill.y1 : detailBar.y1;
    let searchBottom = Math.min(h, searchTop + w * 0.105);
    const limit = Math.min(h, searchTop + Math.round(w * 0.16));
    for (let y = searchTop + Math.round(w * 0.02); y < limit; y++) {
      if (fullRatio[y] >= 0.05) { searchBottom = y; break; }
    }
    natureBox = tightTextBox(px, { x0: w * 0.04, x1: w * 0.50, y0: searchTop, y1: searchBottom });
    notes.push(`せいかく探索 y=${Math.round(searchTop)}..${Math.round(searchBottom)} → ${natureBox ? 'ok' : '見つからず'}`);
  } else {
    notes.push('「詳細ステータス」の見出しバーが見つからず');
  }

  // ---- 名前とSP ------------------------------------------------------------
  // 画面上部。ポケモンをタップした時のポップアップが被っていることもあるので広めに取る。
  const headerBox = { x0: w * 0.02, x1: w * 0.78, y0: h * 0.03, y1: Math.min(h, h * 0.17) };

  return { w, h, headerBox, ingredientSlots, subSkillBoxes, natureBox, notes, bars, pills };
}

export { readPixels, isUiGreen, isCardOrange, isLockBadge };

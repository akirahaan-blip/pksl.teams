/**
 * ポケモンスリープのマスタデータ
 *
 * ここに入れてよいのは「ゲーム側の事実」だけ。
 * 大会の配点や、ツールごとの都合（A/B/Cのようなコード）は入れないこと。
 * 入れてしまうと、そのツール専用のライブラリになって再利用できなくなる。
 */

/** サブスキル17種。short はコミュニティで使われている略称 */
export const SUB_SKILLS = [
  { id: 'kinomi_s',   name: 'きのみの数S',        short: 'きのみS',  aliases: ['きのみS', 'きのみの数'] },
  { id: 'otebo',      name: 'おてつだいボーナス',  short: 'おてぼ',   aliases: ['おてぼ'] },
  { id: 'suimin_bo',  name: '睡眠EXPボーナス',     short: '睡眠ボ',   aliases: ['睡眠ボーナス', '睡眠ボ'] },
  { id: 'risa_bo',    name: 'リサーチEXPボーナス', short: 'リサボ',   aliases: ['リサーチボーナス', 'リサボ'] },
  { id: 'yume_bo',    name: 'ゆめのかけらボーナス', short: 'ゆめボ',   aliases: ['ゆめボ'] },
  { id: 'gen_bo',     name: 'げんき回復ボーナス',   short: 'げんボ',   aliases: ['げんボ'] },
  { id: 'skileve_m',  name: 'スキルレベルアップM',  short: 'スキレベM', aliases: ['スキレベM'] },
  { id: 'skileve_s',  name: 'スキルレベルアップS',  short: 'スキレベS', aliases: ['スキレベS'] },
  { id: 'speed_m',    name: 'おてつだいスピードM',  short: 'スピM',    aliases: ['スピM', 'おてスピM'] },
  { id: 'speed_s',    name: 'おてつだいスピードS',  short: 'スピS',    aliases: ['スピS', 'おてスピS'] },
  { id: 'skill_m',    name: 'スキル確率アップM',    short: 'スキM',    aliases: ['スキM', 'スキル確率M'] },
  { id: 'skill_s',    name: 'スキル確率アップS',    short: 'スキS',    aliases: ['スキS', 'スキル確率S'] },
  { id: 'shokuzai_m', name: '食材確率アップM',      short: '食材M',    aliases: ['食材M'] },
  { id: 'shokuzai_s', name: '食材確率アップS',      short: '食材S',    aliases: ['食材S'] },
  { id: 'shoji_l',    name: '最大所持数アップL',    short: '所持L',    aliases: ['所持L'] },
  { id: 'shoji_m',    name: '最大所持数アップM',    short: '所持M',    aliases: ['所持M'] },
  { id: 'shoji_s',    name: '最大所持数アップS',    short: '所持S',    aliases: ['所持S'] }
];

/** 性格が上げ下げする能力 */
export const STATS = {
  speed: 'おてつだいスピード',
  exp: '獲得EXP',
  skill: 'メインスキル発生確率',
  energy: 'げんき回復量',
  ingredient: '食材おてつだい確率',
  none: 'なし'
};

/** 性格25種。up/down は STATS のキー */
export const NATURES = [
  { name: 'さみしがり', up: 'speed',      down: 'energy' },
  { name: 'いじっぱり', up: 'speed',      down: 'ingredient' },
  { name: 'やんちゃ',   up: 'speed',      down: 'skill' },
  { name: 'ゆうかん',   up: 'speed',      down: 'exp' },
  { name: 'ずぶとい',   up: 'energy',     down: 'speed' },
  { name: 'わんぱく',   up: 'energy',     down: 'ingredient' },
  { name: 'のうてんき', up: 'energy',     down: 'skill' },
  { name: 'のんき',     up: 'energy',     down: 'exp' },
  { name: 'ひかえめ',   up: 'ingredient', down: 'speed' },
  { name: 'おっとり',   up: 'ingredient', down: 'energy' },
  { name: 'うっかりや', up: 'ingredient', down: 'skill' },
  { name: 'れいせい',   up: 'ingredient', down: 'exp' },
  { name: 'おだやか',   up: 'skill',      down: 'speed' },
  { name: 'おとなしい', up: 'skill',      down: 'energy' },
  { name: 'しんちょう', up: 'skill',      down: 'ingredient' },
  { name: 'なまいき',   up: 'skill',      down: 'exp' },
  { name: 'おくびょう', up: 'exp',        down: 'speed' },
  { name: 'せっかち',   up: 'exp',        down: 'energy' },
  { name: 'ようき',     up: 'exp',        down: 'ingredient' },
  { name: 'むじゃき',   up: 'exp',        down: 'skill' },
  { name: 'てれや',     up: 'none',       down: 'none' },
  { name: 'がんばりや', up: 'none',       down: 'none' },
  { name: 'すなお',     up: 'none',       down: 'none' },
  { name: 'きまぐれ',   up: 'none',       down: 'none' },
  { name: 'まじめ',     up: 'none',       down: 'none' }
];

/** サブスキルが解放されるレベル（ステータス画面の5枠の並び順） */
export const SUB_SKILL_LEVELS = [10, 25, 50, 70, 80];

/** 食材が解放されるレベル（ステータス画面の3枠の並び順） */
export const INGREDIENT_LEVELS = [1, 30, 60];

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
「ポケスリ最適チーム診断ツール」のデータを作って index.html を組み立てるプログラム。

やること:
  1. ポケモンのデータと日本語名を読み込む
  2. このファイルの中に書いてあるレシピ表（Wikiから取得）を読み取る
  3. mytools/template.html の /*__DATA__*/ の場所にデータを差し込んで
     index.html を書き出す

使い方（PowerShell で）:
    python mytools\build.py

データがおかしいときは、途中でエラーを出して止まります。
「index.html ができた」と表示されたときだけ成功です。
"""

import json
import os
import re
import sys

# ---------------------------------------------------------------
# 場所の設定
# ---------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
# nitoyon さんの pokesleep-tool を clone したフォルダ。読むだけで、一切書き換えない。
IV = os.path.join(os.path.dirname(ROOT), "pokesleep-iv")


def die(msg):
    """エラーを表示して止める。"""
    print("エラー: " + msg, file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------
# 1. 元データを読む
# ---------------------------------------------------------------
def load_json(path):
    if not os.path.exists(path):
        die("ファイルが見つかりません: " + path)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# 元データの置き場所。
#   pokesleep-tool を clone してあればそこから読み、
#   無ければ mytools/source-data.json（書き出してあるコピー）から読む。
#   こうしておけば、pokesleep-tool を持っていない人でも組み立てられる。
CACHE = os.path.join(HERE, "source-data.json")


def load_source():
    need = [
        ("pokemon",  os.path.join(IV, "src", "data", "pokemon.json")),
        ("names_ja", os.path.join(IV, "src", "i18n", "ja", "pokemons.json")),
        ("data_ja",  os.path.join(IV, "src", "i18n", "ja", "data.json")),
        ("skills_ja",os.path.join(IV, "src", "i18n", "ja", "skills.json")),
    ]
    if all(os.path.exists(path) for _, path in need):
        src = {key: load_json(path) for key, path in need}
        with open(CACHE, "w", encoding="utf-8", newline="\n") as f:
            json.dump(src, f, ensure_ascii=False, separators=(",", ":"))
        print("元データ: pokesleep-tool から読み込み、source-data.json に控えを保存しました")
        return src

    if os.path.exists(CACHE):
        print("元データ: mytools/source-data.json（控え）から読み込みました")
        return load_json(CACHE)

    die("元データが見つかりません。\n"
        "  pokesleep-tool を隣のフォルダに clone するか、\n"
        "  mytools/source-data.json を用意してください。")


_src = load_source()
pokemon_raw = _src["pokemon"]
names_ja = _src["names_ja"]["pokemons"]
data_ja = _src["data_ja"]
skills_ja = _src["skills_ja"]["skills"]
ING_JA = data_ja["ingredients"]   # 例: {"apple": "とくせんリンゴ", ...}
TYPE_JA = data_ja["types"]        # 例: {"electric": "でんき", ...}

SPECIALTY_JA = {
    "Berries": "きのみ",
    "Ingredients": "食材",
    "Skills": "スキル",
    "All": "オール",
}

# 食材の日本語名の一覧（レシピ表の検算に使う）
ING_NAMES = set(ING_JA.values())


# ---------------------------------------------------------------
# 2. ポケモンのデータを組み立てる
# ---------------------------------------------------------------
def build_pokemon():
    out = []
    for p in pokemon_raw:
        en = p["name"]
        ja = names_ja.get(en)
        if ja is None:
            die("日本語名が見つかりません: " + en)

        # 幻のポケモン（食材が特殊なもの）は、この簡易版では扱わない
        if p.get("mythIng") is not None:
            continue

        slots = []
        for key in ("ing1", "ing2", "ing3"):
            ing = p.get(key)
            if ing is None:
                slots.append(None)
                continue
            ja_ing = ING_JA.get(ing["name"])
            if ja_ing is None:
                die("食材の日本語名が見つかりません: " + ing["name"])
            slots.append([ja_ing, ing.get("c1", 0), ing.get("c2", 0), ing.get("c3", 0)])

        if slots[0] is None:
            die("食材A がありません: " + en)

        skill_ja = skills_ja.get(p["skill"], {}).get("name", p["skill"])

        out.append({
            "n": ja,
            "t": TYPE_JA.get(p["type"], p["type"]),
            "sp": SPECIALTY_JA.get(p["specialty"], p["specialty"]),
            "f": p["frequency"],
            "ir": p["ingRate"],
            "skr": p["skillRate"],
            "sk": skill_ja,
            "cl": p["carryLimit"],
            "el": p["evolutionLeft"],
            "ec": p["evolutionCount"],
            "ings": slots,
        })

    # 同じ名前が二重に入っていないか確認
    seen = {}
    for x in out:
        if x["n"] in seen:
            die("ポケモン名が重複しています: " + x["n"])
        seen[x["n"]] = True

    out.sort(key=lambda x: x["n"])
    return out


# ---------------------------------------------------------------
# 3. レシピのデータ
#    出典: ポケモンスリープ攻略・検証 Wiki* 「料理/レシピの一覧」
#    2026-08-22 にブラウザで表をそのまま読み取ったもの（Ver.3.7.0 時点）
#    形式:  料理名 @ 食材 名前 ×個数 名前 ×個数 … @ 食材の合計 @ 基礎エナジー
# ---------------------------------------------------------------
RECIPE_TEXT = {
    "カレー": """
ごちゃまぜカレー @ 他のレシピに該当しない組み合わせ @ - @ 0
とくせんリンゴカレー @ とくせんリンゴ ×7 @ 7 @ 748
あぶりテールカレー @ おいしいシッポ ×8 げきからハーブ ×25 @ 33 @ 7483
サンパワートマトカレー @ あんみんトマト ×10 げきからハーブ ×5 @ 15 @ 2078
ぜったいねむりバターカレー @ ほっこりポテト ×18 あんみんトマト ×15 リラックスカカオ ×12 モーモーミルク ×10 @ 55 @ 9010
からくちネギもりカレー @ ふといながねぎ ×14 あったかジンジャー ×10 げきからハーブ ×8 @ 32 @ 5900
キノコのほうしカレー @ あじわいキノコ ×14 ほっこりポテト ×9 @ 23 @ 4162
おやこあいカレー @ あまいミツ ×12 とくせんリンゴ ×11 とくせんエッグ ×8 ほっこりポテト ×4 @ 35 @ 4523
満腹チーズバーグカレー @ モーモーミルク ×8 マメミート ×8 @ 16 @ 1910
ほっこりホワイトシチュー @ モーモーミルク ×10 ほっこりポテト ×8 あじわいキノコ ×4 @ 22 @ 3181
たんじゅんホワイトシチュー @ モーモーミルク ×7 @ 7 @ 814
マメバーグカレー @ マメミート ×7 @ 7 @ 856
ベイビィハニーカレー @ あまいミツ ×7 @ 7 @ 839
ニンジャカレー @ ワカクサ大豆 ×24 マメミート ×9 ふといながねぎ ×12 あじわいキノコ ×5 @ 50 @ 9445
ひでりカツレツカレー @ マメミート ×10 ピュアなオイル ×5 @ 15 @ 1942
とけるオムカレー @ とくせんエッグ ×10 あんみんトマト ×6 @ 16 @ 2150
ビルドアップマメカレー @ ワカクサ大豆 ×12 マメミート ×6 げきからハーブ ×4 とくせんエッグ ×4 @ 26 @ 3372
じゅうなんコーンシチュー @ ワカクサコーン ×14 モーモーミルク ×8 ほっこりポテト ×8 @ 30 @ 4670
れんごくコーンキーマカレー @ げきからハーブ ×27 マメミート ×24 ワカクサコーン ×14 あったかジンジャー ×12 @ 77 @ 13690
ピヨピヨパンチ辛口カレー @ めざましコーヒー ×11 げきからハーブ ×11 あまいミツ ×11 @ 33 @ 5702
めざめるパワーシチュー @ ワカクサ大豆 ×28 あんみんトマト ×25 あじわいキノコ ×23 めざましコーヒー ×16 @ 92 @ 19061
いあいぎりすき焼きカレー @ ふといながねぎ ×27 マメミート ×26 あまいミツ ×26 とくせんエッグ ×22 @ 101 @ 20655
なりきりバケッチャシチュー @ ずっしりカボチャ ×10 マメミート ×16 ほっこりポテト ×18 あじわいキノコ ×25 @ 69 @ 15621
しんりょくアボカドグラタン @ つやつやアボカド ×22 ほっこりポテト ×20 モーモーミルク ×41 ピュアなオイル ×32 @ 115 @ 24802
ワカクサカレーパン @ あったかジンジャー ×20 げきからハーブ ×20 ワカクサ大豆 ×8 ピュアなオイル ×15 @ 63 @ 10945
とびはねるカレーうどん @ あったかジンジャー ×39 あじわいキノコ ×31 げきからハーブ ×22 マメミート ×20 @ 112 @ 25539
""",
    "サラダ": """
ごちゃまぜサラダ @ 他のレシピに該当しない組み合わせ @ - @ 0
ヤドンテールのペッパーサラダ @ おいしいシッポ ×10 げきからハーブ ×10 ピュアなオイル ×15 @ 35 @ 8169
キノコのほうしサラダ @ あじわいキノコ ×17 あんみんトマト ×8 ピュアなオイル ×8 @ 33 @ 5859
ゆきかきシーザーサラダ @ モーモーミルク ×10 マメミート ×6 @ 16 @ 1898
くいしんぼうポテトサラダ @ ほっこりポテト ×14 とくせんエッグ ×9 マメミート ×7 とくせんリンゴ ×6 @ 36 @ 5040
うるおいとうふサラダ @ ワカクサ大豆 ×15 あんみんトマト ×9 @ 24 @ 3113
ばかぢからワイルドサラダ @ マメミート ×9 あったかジンジャー ×6 とくせんエッグ ×5 ほっこりポテト ×3 @ 23 @ 3046
マメハムサラダ @ マメミート ×8 @ 8 @ 978
あんみんトマトサラダ @ あんみんトマト ×8 @ 8 @ 1045
モーモーカプレーゼ @ モーモーミルク ×12 あんみんトマト ×6 ピュアなオイル ×5 @ 23 @ 2942
ムラっけチョコミートサラダ @ リラックスカカオ ×14 マメミート ×9 @ 23 @ 3665
オーバーヒートサラダ @ げきからハーブ ×17 あったかジンジャー ×10 あんみんトマト ×8 @ 35 @ 5225
とくせんリンゴサラダ @ とくせんリンゴ ×8 @ 8 @ 855
めんえきねぎサラダ @ ふといながねぎ ×10 あったかジンジャー ×5 @ 15 @ 2845
メロメロりんごのチーズサラダ @ とくせんリンゴ ×15 モーモーミルク ×5 ピュアなオイル ×3 @ 23 @ 2655
ニンジャサラダ @ ふといながねぎ ×15 ワカクサ大豆 ×19 あじわいキノコ ×12 あったかジンジャー ×11 @ 57 @ 11659
ねっぷうとうふサラダ @ ワカクサ大豆 ×10 げきからハーブ ×6 @ 16 @ 2114
ワカクササラダ @ ピュアなオイル ×22 ワカクサコーン ×17 あんみんトマト ×14 ほっこりポテト ×9 @ 62 @ 11393
めいそうスイートサラダ @ とくせんリンゴ ×21 あまいミツ ×16 ワカクサコーン ×12 @ 49 @ 7675
みだれづきコーンサラダ @ ワカクサコーン ×9 ピュアなオイル ×8 @ 17 @ 2785
クロスチョップドサラダ @ とくせんエッグ ×20 マメミート ×15 ワカクサコーン ×11 あんみんトマト ×10 @ 56 @ 8755
まけんきコーヒーサラダ @ めざましコーヒー ×28 マメミート ×28 ピュアなオイル ×22 ほっこりポテト ×22 @ 100 @ 20218
はなふぶきミモザサラダ @ とくせんエッグ ×25 ピュアなオイル ×17 ほっこりポテト ×15 マメミート ×12 @ 69 @ 11881
りんごさんヨーグルトサラダ @ とくせんエッグ ×35 とくせんリンゴ ×28 あんみんトマト ×23 モーモーミルク ×18 @ 104 @ 19293
くだけるアボカドサラダ @ つやつやアボカド ×14 ワカクサ大豆 ×18 ピュアなオイル ×10 @ 42 @ 7125
じならしワカモレチップス @ つやつやアボカド ×28 ワカクサコーン ×25 げきからハーブ ×30 ワカクサ大豆 ×22 @ 105 @ 25162
ごろごろねっとうサラダ @ ずっしりカボチャ ×20 ほっこりポテト ×30 ワカクサコーン ×18 あじわいキノコ ×27 @ 95 @ 25356
""",
    "デザート": """
ごちゃまぜジュース @ 他のレシピに該当しない組み合わせ @ - @ 0
じゅくせいスイートポテト @ ほっこりポテト ×9 モーモーミルク ×5 @ 14 @ 1907
ふくつのジンジャークッキー @ あまいミツ ×14 あったかジンジャー ×12 リラックスカカオ ×5 とくせんエッグ ×4 @ 35 @ 4921
とくせんリンゴジュース @ とくせんリンゴ ×8 @ 8 @ 855
クラフトサイコソーダ @ あまいミツ ×9 @ 9 @ 1079
ひのこのジンジャーティー @ あったかジンジャー ×9 とくせんリンゴ ×7 @ 16 @ 1913
プリンのプリンアラモード @ あまいミツ ×20 とくせんエッグ ×15 モーモーミルク ×10 とくせんリンゴ ×10 @ 55 @ 7594
あくまのキッスフルーツオレ @ とくせんリンゴ ×11 モーモーミルク ×9 あまいミツ ×7 リラックスカカオ ×8 @ 35 @ 4734
ねがいごとアップルパイ @ とくせんリンゴ ×12 モーモーミルク ×4 @ 16 @ 1748
ネロリのデトックスティー @ あったかジンジャー ×11 とくせんリンゴ ×15 あじわいキノコ ×9 @ 35 @ 5065
あまいかおりチョコケーキ @ あまいミツ ×9 リラックスカカオ ×8 モーモーミルク ×7 @ 24 @ 3378
モーモーホットミルク @ モーモーミルク ×7 @ 7 @ 814
かるわざソイケーキ @ とくせんエッグ ×8 ワカクサ大豆 ×7 @ 15 @ 1924
はりきりプロテインスムージー @ ワカクサ大豆 ×15 リラックスカカオ ×8 @ 23 @ 3263
マイペースやさいジュース @ あんみんトマト ×9 とくせんリンゴ ×7 @ 16 @ 1924
おおきいマラサダ @ ピュアなオイル ×10 モーモーミルク ×7 あまいミツ ×6 @ 23 @ 3015
ちからもちソイドーナッツ @ ピュアなオイル ×12 ワカクサ大豆 ×16 リラックスカカオ ×7 @ 35 @ 5547
だいばくはつポップコーン @ ワカクサコーン ×15 ピュアなオイル ×14 モーモーミルク ×7 @ 36 @ 6048
おちゃかいコーンスコーン @ とくせんリンゴ ×20 あったかジンジャー ×20 ワカクサコーン ×18 モーモーミルク ×9 @ 67 @ 10925
はなびらのまいチョコタルト @ リラックスカカオ ×11 とくせんリンゴ ×11 @ 22 @ 3314
フラワーギフトマカロン @ リラックスカカオ ×25 とくせんエッグ ×25 あまいミツ ×17 モーモーミルク ×10 @ 77 @ 13834
はやおきコーヒーゼリー @ めざましコーヒー ×16 モーモーミルク ×14 あまいミツ ×12 @ 42 @ 6793
スパークスパイスコーラ @ とくせんリンゴ ×35 あったかジンジャー ×20 ふといながねぎ ×20 めざましコーヒー ×12 @ 87 @ 17494
かたやぶりコーンティラミス @ めざましコーヒー ×14 ワカクサコーン ×14 モーモーミルク ×12 @ 40 @ 7125
ドオーのエクレア @ リラックスカカオ ×30 モーモーミルク ×26 めざましコーヒー ×24 あまいミツ ×22 @ 102 @ 20885
ドキドキこわいかおパンケーキ @ ずっしりカボチャ ×18 とくせんエッグ ×24 あまいミツ ×32 あんみんトマト ×29 @ 103 @ 24354
グラスミキサースムージー @ つやつやアボカド ×18 あんみんトマト ×16 モーモーミルク ×14 @ 48 @ 8165
みつあつめチョコワッフル @ あまいミツ ×38 ワカクサコーン ×28 ピュアなオイル ×28 リラックスカカオ ×21 @ 115 @ 25484
""",
}

# 期待する品数。Wiki の表の行数と合っているかを確かめるための保険。
EXPECTED_COUNT = {"カレー": 26, "サラダ": 27, "デザート": 28}


def build_recipes():
    out = []
    for cat, text in RECIPE_TEXT.items():
        lines = [ln.strip() for ln in text.strip().split("\n") if ln.strip()]
        if len(lines) != EXPECTED_COUNT[cat]:
            die("%s の品数が %d 品です（%d 品のはず）" %
                (cat, len(lines), EXPECTED_COUNT[cat]))

        for ln in lines:
            parts = [x.strip() for x in ln.split("@")]
            if len(parts) != 4:
                die("行の形がおかしいです: " + ln)
            name, ing_text, total_text, energy_text = parts

            # 「ごちゃまぜ」は食材の決まりがないので、候補から外す
            if "該当しない組み合わせ" in ing_text:
                continue

            # 「とくせんリンゴ ×7」の並びを取り出す
            pairs = re.findall(r"([^\s×]+)\s*×(\d+)", ing_text)
            if not pairs:
                die("食材が読み取れません: " + ln)

            ings = {}
            for ing_name, cnt in pairs:
                if ing_name not in ING_NAMES:
                    die("知らない食材が出てきました: 「%s」（%s）" % (ing_name, name))
                if ing_name in ings:
                    die("同じ食材が2回出てきます: " + name)
                ings[ing_name] = int(cnt)

            # 合計個数が Wiki の「計」の列と合うか検算する
            total = sum(ings.values())
            if total != int(total_text):
                die("%s: 食材の合計が %d ですが、Wiki の「計」は %s です" %
                    (name, total, total_text))

            out.append({
                "n": name,
                "cat": cat,
                "ings": ings,
                "total": total,
                "e": int(energy_text),
            })

    names = [r["n"] for r in out]
    if len(names) != len(set(names)):
        die("料理名が重複しています")
    return out


# ---------------------------------------------------------------
# 4. フィールドと「カビゴンの好きなきのみ」
#    出典: ポケらく（2026-08-22 時点）。きのみはタイプと1対1で対応する。
# ---------------------------------------------------------------
BERRY_BY_TYPE = {
    "ノーマル": "キーのみ", "ほのお": "ヒメリのみ", "みず": "オレンのみ",
    "でんき": "ウブのみ", "くさ": "ドリのみ", "こおり": "チーゴのみ",
    "かくとう": "クラボのみ", "どく": "カゴのみ", "じめん": "フィラのみ",
    "ひこう": "シーヤのみ", "エスパー": "マゴのみ", "むし": "ラムのみ",
    "いわ": "オボンのみ", "ゴースト": "ブリーのみ", "ドラゴン": "ヤチェのみ",
    "あく": "ウイのみ", "はがね": "ベリブのみ", "フェアリー": "モモンのみ",
}

# ex: EXフィールドの種類。None なら通常フィールド
FIELDS = [
    {"n": "ワカクサ本島", "types": None, "ex": None},   # 毎週ランダム。自分で選ぶ
    {"n": "シアンの砂浜", "types": ["みず", "フェアリー", "ひこう"], "ex": None},
    {"n": "トープ洞窟", "types": ["ほのお", "じめん", "いわ"], "ex": None},
    {"n": "ウノハナ雪原", "types": ["こおり", "ノーマル", "あく"], "ex": None},
    {"n": "ラピスラズリ湖畔", "types": ["くさ", "エスパー", "かくとう"], "ex": None},
    {"n": "ゴールド旧発電所", "types": ["でんき", "ゴースト", "はがね"], "ex": None},
    {"n": "アンバー渓谷", "types": ["どく", "むし", "ドラゴン"], "ex": None},
    # EXフィールド。好みのきのみが「メイン1つ＋サブ2つ」に分かれる
    {"n": "ワカクサ本島 EX", "types": None, "ex": "ggex"},
    {"n": "シアンの砂浜 EX", "types": ["みず", "フェアリー", "ひこう"], "ex": "cbex"},
]

# EXフィールドの週替わりバフ（出典: pokesleep-tool の PokemonStrength.ts）
#   好みのきのみ（メイン・サブどちらでも）を持つポケモンだけが対象。
#   berry … きのみエナジーの倍率が 2倍 → 2.4倍 になる
#   ing   … 食材おてつだいのたびに +1個。食材とくい／オールはさらに50%の確率で+1（平均+1.5）
#   skill … メインスキルの発動確率が 1.25倍
#   また、バフの種類に関係なく「メインの好みのきのみ」はスキルレベルが +1 される。
EX_EFFECT = {
    "berry": {"label": "きのみエナジー 2.4倍", "berryMul": 2.4},
    "ing":   {"label": "食材 +1個（食材とくいは平均+1.5）", "ing": 1, "ingExtra": 0.5},
    "skill": {"label": "スキル確率 1.25倍", "skillMul": 1.25},
}
EX_MAIN_SKILL_LEVEL_BONUS = 1

# EXフィールドのおてつだいスピード補正（出典: pokesleep-tool の PokemonStrength.ts）
#   main    … メインの好みのきのみ。おてつだい間隔がこの割合だけ短くなる
#   non     … 好みでないきのみ。おてつだい間隔がこの割合だけ長くなる
EX_BONUS = {
    "ggex": {"main": 0.10, "non": 0.15},   # ワカクサ本島EX
    "cbex": {"main": 0.20, "non": 0.35},   # シアンの砂浜EX
}

# レシピレベルのボーナス（％）。出典: pokesleep-tool の PokemonStrength.ts
RECIPE_LEVEL_BONUS = {
    1:0, 2:2, 3:4, 4:6, 5:8, 6:9, 7:11, 8:13, 9:16, 10:18,
    11:19, 12:21, 13:23, 14:24, 15:26, 16:28, 17:30, 18:31, 19:33, 20:35,
    21:37, 22:40, 23:42, 24:45, 25:47, 26:50, 27:52, 28:55, 29:58, 30:61,
    31:64, 32:67, 33:70, 34:74, 35:77, 36:81, 37:84, 38:88, 39:92, 40:96,
    41:100, 42:104, 43:108, 44:113, 45:117, 46:122, 47:127, 48:132, 49:137, 50:142,
    51:148, 52:153, 53:159, 54:165, 55:171, 56:177, 57:183, 58:190, 59:197, 60:203,
    61:209, 62:215, 63:221, 64:227, 65:234, 66:239, 67:243, 68:248, 69:252, 70:258,
}


# ---------------------------------------------------------------
# 4-2. なべ（鍋）まわり
#   出典: ポケモンスリープ攻略・検証 Wiki*「なべ」（2026-08-22 に確認）
#   なべに入れられる食材の数
#     = {(なべ容量 × イベント × ウィークエンド) + 料理パワーアップ増加分}
#       × いいキャンプチケット(1.5)   ※最後に四捨五入
# ---------------------------------------------------------------
POT_SIZES = [21, 23, 25, 27, 29, 31, 33, 36, 39, 42, 45, 48,
             51, 54, 57, 60, 63, 66, 69, 72, 75, 78, 81]

# 料理パワーアップS の増加量（スキルレベル1〜7）
#   出典: pokesleep-tool の MainSkill.ts
COOKING_UP = {
    "料理パワーアップS": [7, 10, 12, 17, 22, 27, 31],
    "マイナス (料理パワーアップS)": [5, 7, 9, 12, 16, 20, 24],
}

# 食材ゲットS が1回の発動でもらえる食材の数（スキルレベル1〜7）
#   出典: pokesleep-tool の MainSkill.ts
#   ゲーム内の説明「入手したことのある食材の中から3種類を均等に取得します」
#   → どの3種類かはランダムなので、19種に均等にならして計算する
INGREDIENT_MAGNET = {
    "食材ゲットS": [6, 8, 11, 14, 17, 21, 24],
    "プラス (食材ゲットS)": [5, 7, 9, 11, 13, 16, 18],
    "プレゼント (食材ゲットS)": [4, 6, 8, 10, 12, 15, 17],
}

# 「プラス」「マイナス」を持つポケモンが自分以外にチームにいるときの追加効果
#   プラス側: 追加で自分の1枠目の食材をもらう（個数は本人の実プレイ情報 2026-08-23）
#   マイナス側: 料理パワーアップに加えて げんきエールS も出る（げんきは未実装なので効かない）
PLUS_BONUS_COUNT = 14

# 食材の種類数（食材ゲットSをならすのに使う）
ING_KINDS = 19

# ---------------------------------------------------------------
# ナイトキャップをかぶったピカチュウ（Pokémon GO Plus+ の連携特典）
#   出典: ポケモンスリープ攻略・検証 Wiki*「PokémonGOPlus+」（2026-08-24 確認）
#   ・チーム編成の枠を使わない（実質6匹目）
#   ・レベルの代わりに「なつき度」1〜20。きのみエナジーは なつき度＝レベル で計算
#   ・げんきの概念がなく、表の時間どおりの間隔でおてつだいする
#   ・せいかく・メインスキル・サブスキルなし
#   ・きのみは ウブのみ（でんき）。好みのきのみなら2倍になる
#   ・食材は A=とくせんリンゴ / B=リラックスカカオ / C=あまいミツ
# 形式: なつき度: [おてつだい間隔(秒), 最大所持数, きのみの数, A, B, C]
# ---------------------------------------------------------------
NIGHTCAP = {
    1:  [4800,  8, 1, 0, 0, 0],
    2:  [4680,  8, 1, 0, 0, 0],
    3:  [4560,  9, 1, 1, 0, 0],
    4:  [4440,  9, 1, 1, 0, 0],
    5:  [4380, 10, 1, 1, 0, 0],
    6:  [4320, 10, 1, 1, 0, 0],
    7:  [4260, 11, 1, 1, 0, 0],
    8:  [4200, 11, 1, 1, 0, 0],
    9:  [4140, 12, 1, 1, 1, 0],
    10: [4080, 12, 1, 1, 1, 0],
    11: [4020, 13, 2, 1, 1, 0],
    12: [3960, 13, 2, 1, 1, 0],
    13: [3900, 14, 2, 2, 1, 0],
    14: [3840, 14, 2, 2, 1, 0],
    15: [3780, 15, 2, 2, 1, 0],
    16: [3720, 15, 2, 2, 1, 0],
    17: [3660, 16, 2, 2, 2, 0],
    18: [3600, 16, 2, 2, 2, 0],
    19: [3570, 17, 2, 2, 2, 2],
    20: [3540, 17, 2, 2, 2, 2],
}

NIGHTCAP_INFO = {
    "ings": ["とくせんリンゴ", "リラックスカカオ", "あまいミツ"],
    "type": "でんき",
    # 食材を拾う確率。Wiki の検証データ（329回中 食材109回＝約33%）。
    # なつき度19以上は3枠目のあまいミツが増えるぶん確率が上がり、
    # Wiki の「なつき度20で1日あたり リンゴ12・カカオ5・ミツ3」と合うのは41%。
    "ingRate": {"base": 0.33, "high": 0.41},
    # どの枠が選ばれるかの比。上の「12:5:3」から
    "slotWeight": [12, 5, 3],
    # 1日1回、ポケストップを回した数でもらえるウブのみの数
    "stopBerries": [[7, 6], [15, 8], [23, 10], [31, 12], [9999, 14]],
}

# ---------------------------------------------------------------
# カバン（最大所持数）
#   出典: pokesleep-tool の PokemonIv.ts / HelpCount.ts
#   上限 = ポケモンの基本値 + 5×進化回数 + 寝顔リボン + 最大所持数アップ×6
#          （いいキャンプチケットで ×1.2）
#   カバンがいっぱいになると「つまみ食い」になり、
#   きのみだけをカビゴンに直接渡す（＝食材が入らない）
# ---------------------------------------------------------------
BAG = {
    "perEvolution": 5,      # 進化1回につき +5
    "perInventorySub": 6,   # 最大所持数アップ1段階につき +6
    "ribbon": [0, 1, 3, 6, 8],  # 寝顔リボン 0〜4 での増加
    "ticketMul": 1.2,       # いいキャンプチケット
}

# ---------------------------------------------------------------
# げんき（元気）のしくみ
#   出典: pokesleep-tool の Energy.ts
#   ・起きている間は 10分で 1% 減る
#   ・げんきが高いほど、おてつだいの間隔が短くなる
#   ・睡眠で回復する（睡眠スコア100＝510分で100%）
# ---------------------------------------------------------------
ENERGY = {
    # [げんきがこの値より大きければ, おてつだい間隔の倍率]
    "rate": [[80, 0.45], [60, 0.52], [40, 0.58], [1, 0.66], [-1, 1.0]],
    "decayPer10min": 1,      # 起きている間、10分で1%減る
    "wakeMax": 100,          # 起床時の上限
    "wakeMaxWithBonus": 105, # げんき回復ボーナスを持っていると105
    "recoveryBonusPer": 0.14,# げんき回復ボーナス1つにつき +14%
    "sleepFullMinutes": 510, # 睡眠スコア100にあたる分数
}

# げんきを回復させるメインスキル（スキルレベル1〜6）
#   target: all=チーム全員 / one=チームからランダムに1匹 / self=自分だけ
HEALERS = {
    "げんきオールS":                  {"v": [5, 7, 9, 11, 15, 18], "target": "all"},
    "みかづきのいのり (げんきオールS)": {"v": [3, 4, 5, 7, 9, 11],   "target": "all"},
    "きのみジュース (げんきオールS)":   {"v": [5, 7, 9, 11, 15, 18], "target": "all"},
    "げんきエールS":                  {"v": [12, 15, 20, 25, 33, 44], "target": "one"},
    "ほっぺすりすり (げんきエールS)":   {"v": [9, 12, 16, 20, 27, 35],  "target": "one"},
    "いやしのはどう (げんきエールS)":   {"v": [6, 8, 10, 13, 17, 22],   "target": "one"},
    "げんきチャージS":                {"v": [12, 16, 21, 27, 34, 43], "target": "self"},
    "つきのひかり (げんきチャージS)":   {"v": [12, 16, 21, 27, 34, 43], "target": "self"},
}

# マイナス（料理パワーアップS）は、対になる子がいると げんきエールS も出る
MINUS_CHEER = [12, 15, 20, 25, 33, 44]

# 料理チャンスS が上げる大成功率（％、スキルレベル1〜6）
#   出典: pokesleep-tool の MainSkill.ts
TASTY_CHANCE = {
    "料理チャンスS": [4, 5, 6, 7, 8, 10],
}

# 料理の大成功
#   出典: ポケモンスリープ攻略・検証 Wiki*「料理」（2026-08-23 に確認）
#   月〜土は 10% で2倍、日曜は 30% で3倍。料理チャンスSで最大 +70% まで上げられる。
GREAT_SUCCESS = {
    "weekday": {"rate": 10, "mult": 2},
    "sunday":  {"rate": 30, "mult": 3},
    "chanceMax": 70,          # 料理チャンスSで足せる上限（％）
    "sundayPotMul": 2,        # 日曜はなべ容量が2倍（ウィークエンドボーナス）
}


def check_cooking_skills(pokemon):
    """料理パワーアップ・料理チャンスを持つポケモンが実在するか確かめる。"""
    found = {k: 0 for k in list(COOKING_UP) + list(TASTY_CHANCE)
             + list(INGREDIENT_MAGNET) + list(HEALERS)}
    for p in pokemon:
        if p["sk"] in found:
            found[p["sk"]] += 1
    for k, v in found.items():
        if v == 0:
            die("「%s」を持つポケモンが1匹も見つかりません（スキル名が変わった？）" % k)
    return found


# ---------------------------------------------------------------
# 4-3. せいかく と サブスキル（個体値計算機のCSVを読むために使う）
#   出典: pokesleep-tool の Nature.ts / SubSkill.ts
# ---------------------------------------------------------------
# げんき回復量が上がる／下がる性格
ENERGY_UP   = ["Bold", "Impish", "Lax", "Relaxed"]
ENERGY_DOWN = ["Hasty", "Lonely", "Gentle", "Mild"]
# おてつだいスピードが上がる／下がる性格
SPEED_UP   = ["Lonely", "Adamant", "Naughty", "Brave"]
SPEED_DOWN = ["Bold", "Timid", "Calm", "Modest"]
# 食材おてつだい確率が上がる／下がる性格
ING_UP     = ["Modest", "Mild", "Rash", "Quiet"]
ING_DOWN   = ["Impish", "Jolly", "Adamant", "Careful"]
# メインスキル発生確率が上がる／下がる性格
SKILL_UP   = ["Calm", "Gentle", "Careful", "Sassy"]
SKILL_DOWN = ["Lax", "Naive", "Naughty", "Rash"]
# EXP獲得量が上がる／下がる性格。
# このツールの計算には使わないが、せいかくをえらぶ画面に出すために持っている
EXP_UP     = ["Timid", "Hasty", "Jolly", "Naive"]
EXP_DOWN   = ["Relaxed", "Brave", "Sassy", "Quiet"]


def build_natures():
    """{日本語のせいかく名: {speed, ing, skill}} を作る。値は 1=上がる / -1=下がる / 0=なし"""
    nat_ja = data_ja["natures"]        # 例: {"Lonely": "さみしがり", ...}
    out = {}
    for en, ja in nat_ja.items():
        out[ja] = {
            "speed": 1 if en in SPEED_UP else -1 if en in SPEED_DOWN else 0,
            "ing":   1 if en in ING_UP   else -1 if en in ING_DOWN   else 0,
            "skill": 1 if en in SKILL_UP else -1 if en in SKILL_DOWN else 0,
            "energy": 1 if en in ENERGY_UP else -1 if en in ENERGY_DOWN else 0,
            "exp":   1 if en in EXP_UP   else -1 if en in EXP_DOWN   else 0,
        }

    # 上がる／下がるが全部そろっているか確認する
    for name, lst in [("SPEED_UP", SPEED_UP), ("SPEED_DOWN", SPEED_DOWN),
                      ("ING_UP", ING_UP), ("ING_DOWN", ING_DOWN),
                      ("SKILL_UP", SKILL_UP), ("SKILL_DOWN", SKILL_DOWN),
                      ("ENERGY_UP", ENERGY_UP), ("ENERGY_DOWN", ENERGY_DOWN),
                      ("EXP_UP", EXP_UP), ("EXP_DOWN", EXP_DOWN)]:
        for en in lst:
            if en not in nat_ja:
                die("せいかく「%s」（%s）の日本語名が見つかりません" % (en, name))

    if len(out) != 25:
        die("せいかくが %d 種類しかありません（25種類のはず）" % len(out))
    return out


def build_subskills():
    """{日本語のサブスキル名: [種類, 個数]} を作る。個数は S=1 / M=2"""
    sub_ja = data_ja["subskill"]
    want = {
        "Helping Speed S": ["speed", 1], "Helping Speed M": ["speed", 2],
        "Ingredient Finder S": ["ing", 1], "Ingredient Finder M": ["ing", 2],
        "Skill Trigger S": ["skill", 1], "Skill Trigger M": ["skill", 2],
        "Helping Bonus": ["helpbonus", 1],
        "Berry Finding S": ["berry", 1],
        "Energy Recovery Bonus": ["recovery", 1],
        "Inventory Up S": ["inventory", 1],
        "Inventory Up M": ["inventory", 2],
        "Inventory Up L": ["inventory", 3],
    }
    out = {}
    for en, v in want.items():
        ja = sub_ja.get(en)
        if ja is None:
            die("サブスキル「%s」の日本語名が見つかりません" % en)
        out[ja] = v
    return out


# サブスキルが使えるようになるレベル（出典: SubSkillList.ts）
SUBSKILL_LEVELS = [10, 25, 50, 70, 80]


def check_ing_kinds():
    if len(ING_NAMES) != ING_KINDS:
        die("食材が %d 種類あります（%d 種類のはず）" % (len(ING_NAMES), ING_KINDS))


def check_fields():
    for f in FIELDS:
        if f.get("ex") is not None and f["ex"] not in EX_BONUS:
            die("知らないEXフィールドです: " + str(f["ex"]))
        if f["types"] is None:
            continue
        for t in f["types"]:
            if t not in BERRY_BY_TYPE:
                die("知らないタイプです: " + t)
    # ポケモンのタイプが全部きのみ表に入っているか確認
    for t in set(TYPE_JA.values()):
        if t not in BERRY_BY_TYPE:
            die("きのみが決まっていないタイプがあります: " + t)


# ---------------------------------------------------------------
# 4-4. スクショ読み取りライブラリ（pokesleep-vision）を1つにまとめる
#   もとは import / export で分かれた5つのファイル。
#   index.html はファイルを直接開いて使うので、そのままでは読み込めない
#   （ブラウザの決まりで、file:// では import が使えない）。
#   そこで import / export を取り除いて1つにつなぎ、
#   window.PSVision から使えるようにする。
# ---------------------------------------------------------------
VISION_DIR = os.path.join(HERE, "vision")
VISION_ORDER = ["gamedata.js", "layout.js", "matching.js", "ingredients.js", "index.js"]


def build_vision():
    if not os.path.isdir(VISION_DIR):
        die("スクショ読み取りのフォルダがありません: " + VISION_DIR)

    parts = []
    for name in VISION_ORDER:
        path = os.path.join(VISION_DIR, name)
        if not os.path.exists(path):
            die("スクショ読み取りのファイルがありません: " + path)
        with open(path, encoding="utf-8") as f:
            code = f.read()

        out_lines = []
        skipping = False
        for line in code.split("\n"):
            st = line.strip()
            # 「import 〜 from '...';」を丸ごと外す（複数行のこともある）
            if skipping:
                if "from" in st and st.endswith(";"):
                    skipping = False
                continue
            if st.startswith("import "):
                if not (st.endswith(";") and " from " in st):
                    skipping = True
                continue
            # 「export { a, b } from '...';」のような再輸出も外す
            if st.startswith("export {") or st.startswith("export *"):
                if not st.endswith(";"):
                    skipping = True
                continue
            # 「export const X」「export function f」→ export を外すだけ
            if st.startswith("export "):
                line = line.replace("export ", "", 1)
            out_lines.append(line)

        parts.append("/* ---- " + name + " ---- */\n" + "\n".join(out_lines))

    body = "\n\n".join(parts)
    return ("(function(){\n" + body +
            "\n  window.PSVision = { readStatusScreen, initOCR, detectLayout, classifyIngredientSlot, readPixels };\n})();")


# ---------------------------------------------------------------
# 5. index.html を書き出す
# ---------------------------------------------------------------
def main():
    pokemon = build_pokemon()
    recipes = build_recipes()
    check_fields()
    cooking = check_cooking_skills(pokemon)
    check_ing_kinds()
    natures = build_natures()
    subskills = build_subskills()

    print("ポケモン: %d 匹" % len(pokemon))
    for cat in EXPECTED_COUNT:
        n = len([r for r in recipes if r["cat"] == cat])
        print("  %s: %d 品（ごちゃまぜを除く）" % (cat, n))
    for k, v in cooking.items():
        print("  %s: %d 匹" % (k, v))
    print("せいかく: %d 種類 / サブスキル対応表: %d 件" % (len(natures), len(subskills)))

    def dump(obj):
        return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))

    data_js = "\n".join([
        "const POKEMON = %s;" % dump(pokemon),
        "const RECIPES = %s;" % dump(recipes),
        "const FIELDS = %s;" % dump(FIELDS),
        "const BERRY_BY_TYPE = %s;" % dump(BERRY_BY_TYPE),
        "const ING_LIST = %s;" % dump(sorted(ING_NAMES)),
        "const POT_SIZES = %s;" % dump(POT_SIZES),
        "const COOKING_UP = %s;" % dump(COOKING_UP),
        "const TASTY_CHANCE = %s;" % dump(TASTY_CHANCE),
        "const INGREDIENT_MAGNET = %s;" % dump(INGREDIENT_MAGNET),
        "const PLUS_BONUS_COUNT = %d;" % PLUS_BONUS_COUNT,
        "const ING_KINDS = %d;" % ING_KINDS,
        "const BAG = %s;" % dump(BAG),
        "const NIGHTCAP = %s;" % dump(NIGHTCAP),
        "const NIGHTCAP_INFO = %s;" % dump(NIGHTCAP_INFO),
        "const ENERGY = %s;" % dump(ENERGY),
        "const HEALERS = %s;" % dump(HEALERS),
        "const MINUS_CHEER = %s;" % dump(MINUS_CHEER),
        "const GREAT_SUCCESS = %s;" % dump(GREAT_SUCCESS),
        "const NATURES = %s;" % dump(natures),
        "const SUBSKILLS = %s;" % dump(subskills),
        "const SUBSKILL_LEVELS = %s;" % dump(SUBSKILL_LEVELS),
        "const EX_BONUS = %s;" % dump(EX_BONUS),
        "const EX_EFFECT = %s;" % dump(EX_EFFECT),
        "const EX_MAIN_SKILL_LEVEL_BONUS = %d;" % EX_MAIN_SKILL_LEVEL_BONUS,
        "const RECIPE_LEVEL_BONUS = %s;" % dump(RECIPE_LEVEL_BONUS),
    ])

    vision = build_vision()

    tpl_path = os.path.join(HERE, "template.html")
    if not os.path.exists(tpl_path):
        die("template.html がありません: " + tpl_path)
    with open(tpl_path, encoding="utf-8") as f:
        tpl = f.read()

    if "/*__DATA__*/" not in tpl:
        die("template.html に /*__DATA__*/ の目印がありません")

    if "/*__VISION__*/" not in tpl:
        die("template.html に /*__VISION__*/ の目印がありません")

    html = tpl.replace("/*__DATA__*/", data_js).replace("/*__VISION__*/", vision)

    out_path = os.path.join(ROOT, "index.html")
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)

    print("")
    print("index.html ができました → " + out_path)
    print("大きさ: %.0f KB" % (os.path.getsize(out_path) / 1024))
    print("スクショ読み取り: %d ファイルを組み込みました" % len(VISION_ORDER))

    build_icons()


# ---------------------------------------------------------------
# アイコン。teams.png（1枚）から、必要な大きさをまとめて作る。
#   ・favicon-32.png       ブラウザのタブ
#   ・icon-192 / icon-512  Android や「ホーム画面に追加」
#   ・apple-touch-icon     iPhone の「ホーム画面に追加」
# teams.png を差し替えたら、build.py を動かせば全部作り直される。
# Pillow が入っていない環境でも止まらないようにしてある
# （その場合はいまある画像がそのまま使われる）。
# ---------------------------------------------------------------
ICON_SIZES = [(512, "icon-512.png"), (192, "icon-192.png"),
              (180, "apple-touch-icon.png"), (32, "favicon-32.png")]


def build_icons():
    src_path = os.path.join(ROOT, "teams.png")
    if not os.path.exists(src_path):
        print("アイコン: teams.png が無いので、そのままにしました")
        return
    try:
        from PIL import Image
    except ImportError:
        print("アイコン: Pillow が無いので作り直しませんでした（いまある画像を使います）")
        return

    src = Image.open(src_path).convert("RGB")
    if src.size[0] != src.size[1]:
        print("アイコン: teams.png が正方形ではありません（%dx%d）。"
              "正方形にするときれいに出ます" % src.size)
    made = []
    for size, name in ICON_SIZES:
        src.resize((size, size), Image.LANCZOS).save(
            os.path.join(ROOT, name), optimize=True)
        made.append(name)
    print("アイコン: %s を teams.png から作りました" % "、".join(made))


if __name__ == "__main__":
    main()

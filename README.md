# slopscope

AI が作ったっぽい「雑さ（slop）」と、数字で測れる使いにくさを、2 段で監査する Agent Skill です。直す前と後も比べます。

*An Agent Skill that audits a web page for AI-looking "slop" (opinion) and measurable usability problems (fact), then compares before and after a fix.*

## できること

| 段 | 中身 | 性質 |
|---|---|---|
| 見た目の監査（V-01〜V-09） | グラデーションや光るぼかし、絵文字のラベル、誇大な文言、ばらばらの余白、和文と欧文の混ざり方、和文の行の高さ | 意見（理由つき） |
| 計測（M-01〜M-09） | 文字のコントラスト、キーボードで選んだときの枠が見えるか、枠の欠け、375px での横はみ出し、iPhone の入力時の拡大、名前のない操作部品、押せる大きさ、動きを減らす設定、色・文字サイズ・余白の種類の数 | 事実（数字・基準・場所） |
| 前後比較 | 直す前と後の計測と画像を比べて、悪くなった項目を一番上に出す | 事実 |

監査して、方向性を提案したら止まります。直すのは頼まれたときだけです。

## 入れ方

Claude Code（すべてのプロジェクトで使う場合）：

```bash
git clone https://github.com/kajisho5/slopscope
```

```bash
cp -r slopscope/skills/slopscope ~/.claude/skills/
```

1 つのプロジェクトだけで使う場合は、そのプロジェクトの `.claude/skills/` にコピーします。

計測に必要なもの（Python 3.11 以上）：

```bash
python3 -m pip install -r slopscope/requirements.txt
```

```bash
python3 -m playwright install chromium
```

## 使い方

Claude Code で「このページを slopscope で監査して」と頼むか、`/slopscope` を呼びます。結果は `slopscope-report/` に出ます。

スクリプトだけを直接使うこともできます：

```bash
python3 skills/slopscope/scripts/measure.py https://example.invalid/ --out slopscope-report/measure.json
```

```bash
python3 skills/slopscope/scripts/compare.py before/measure.json after/measure.json
```

## 確かめていること・いないこと

- `examples/sloppy.html`（問題をわざと入れた架空のページ）で M-01〜M-08 がすべて不合格に、`examples/fixed.html` ですべて合格になることを、GitHub Actions で毎回確かめています。
- 計測は Chromium だけです。スクリーンリーダー、Safari・Firefox、実機、200% 拡大、最初の表示で見えない状態（開いたメニューなど）は確かめません。報告にも毎回そう書きます。
- claude.ai のチャット上で動くかは確かめていません。

## 出典

見た目の監査で「AI っぽさのしるし」を名前を付けて洗い出す考え方は、Damir Sokolovsky さんの [unslop](https://github.com/heydamir/unslop)（CC BY 4.0）にならっています。項目の文章と計測は slopscope 用に書いたものです。計測の手法は [KATA UI](https://github.com/kajisho5/KATA-UI) の検査ツールから移しました。

設計書：[docs/DESIGN.md](docs/DESIGN.md)

## ライセンス

MIT

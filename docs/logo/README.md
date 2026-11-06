# ロゴ

使うファイルは `assets/` にあります。

| ファイル | 使う場所 |
|---|---|
| `app-icon.svg` | 角丸の四角に入れたアイコン（README の一番上、明るい背景でも暗い背景でも使える） |
| `logo.svg` / `logo-dark.svg` | マークだけ（小さい場所） |
| `wordmark.svg` / `wordmark-dark.svg` | 名前だけ |
| `lockup.svg` / `lockup-dark.svg` | マークと名前を横に並べたもの |
| `social-preview.png` / `social-preview-ja.png` | リンクを共有したときに出る画像（1280×640）。英語版と日本語版 |

`-dark` は暗い背景用です。

README の画面の画像 `docs/images/demo.png` は、`python3 docs/images/make_demo.py` で撮り直せます（架空の見本ページを実際に測った結果）。共有用の画像は `docs/logo/social/social-preview.html`（英語）と `social-preview-ja.html`（日本語）を、ブラウザで 1280×640 で撮ったものです。黒地に、雑な見本画面を照準と引き出し線で測った図を置いています。選ばなかった朱色のポスター案は `docs/logo/social/b-poster.*` にあります。

## 形の意味

照準（ねらいを定める丸と目盛り）の下から、しずくが垂れています。「雑なところ（slop）にねらいを付けて見る」という意味です。名前のロゴでは、scope の o が照準の丸になっています。

- 色：黒 `#18181B`、朱色 `#FF4F2E`（暗い背景では `#F4F4F5` と `#FF7A5C`）
- 文字：Inter Bold を線の形に直したもの。Inter は SIL Open Font License 1.1 で、ロゴへの利用は自由です
- 作り直すとき：`python3 docs/logo/make.py docs/logo/concepts assets`（fontTools が必要）

## ほかの案

`concepts/` に、選ばなかった案も置いています。`concepts/preview.html` をブラウザで開くと並べて見られます。

| 案 | 意味 |
|---|---|
| reticle（採用） | 照準としずく |
| ruler | 中に目盛りのある虫めがね（推測でなく測る） |
| halflens | 半分塗り・半分線のレンズ（事実と意見の 2 つの見方） |
| sscope | S の上の丸に焦点の点 |
| wordmark | 名前だけ |

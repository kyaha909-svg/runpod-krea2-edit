# Krea 2 Identity Edit V2 画像編集 — RunPod ワンクリックテンプレート

Comfy-Org の **Krea 2 Turbo**（fp8）と、コミュニティ製 **Identity Edit LoRA V2**
（`conradlocke/krea2-identity-edit`）＋ 専用カスタムノード
`lbouaraba/comfyui-krea2edit` を使って、ComfyUI で**人物の同一性を保ったまま
写真を再構成する画像編集**（人物写真＋編集指示 → 編集結果）ができる RunPod Pod テンプレートです。

- モデルはイメージに焼き込まず、**初回起動時に永続ボリューム `/workspace` へ自動ダウンロード**（約20.5GB）。2回目以降は即起動します
- Identity Edit 専用ワークフローを同梱し、ComfyUI の Workflow メニューからそのまま開けます
- 1枚の人物写真からの再配置（restage）が基本形で、参照2枚によるシーンへの人物合成にも対応します

## 含まれるモデル（初回起動時に自動DL）

| 役割 | ファイル | サイズ | 取得元 |
|---|---|---|---|
| 本体 Turbo | `krea2_turbo_fp8_scaled.safetensors` | 13.14GB | Comfy-Org/Krea-2 |
| テキストエンコーダー | `qwen3vl_4b_fp8_scaled.safetensors` | 5.24GB | Comfy-Org/Krea-2 |
| VAE | `qwen_image_vae.safetensors` | 0.25GB | Comfy-Org/Krea-2 |
| Identity Edit LoRA V2 | `loras/Krea2/krea2_identity_edit_v2.safetensors` | 1.83GB | conradlocke/krea2-identity-edit |

合計：13.14＋5.24＋0.25＋1.83 ＝ **約20.5GB**。全て公開リポジトリで、HF_TOKEN は不要です。
テキストエンコーダーは CLIPLoader の type を **`krea2`** にしないと動作しません（ワークフローには設定済み）。

## ファイル構成

```
Dockerfile            ベース: runpod/pytorch (CUDA 12.8) + ComfyUI最新版 + comfyui-krea2edit + Manager
start.sh              初回DL → /workspace へ配置 → ComfyUI起動 (8188) / JupyterLab (8888)
workflows/
  krea2_identity_edit.json           Identity Edit（UI形式・Turbo・参照2枚対応）
  api/krea2_identity_edit_api.json   API形式（1枚）
runpod-template.json  テンプレート定義（API作成用）
create_template.py    RUNPOD_API_KEY でテンプレートをAPI作成するスクリプト
test_edit.py          ブラウザなしで編集を1回実行する確認用クライアント
build_workflows.py    ワークフローJSONの生成元（直す場合はこちらを編集して再実行）
```

## 手順1：Dockerイメージを build & push

```bash
cd runpod-krea2-edit
docker build -t ghcr.io/kyaha909-svg/krea2-edit:latest .
docker push ghcr.io/kyaha909-svg/krea2-edit:latest
```

GitHub に push した場合は `.github/workflows/docker-build.yml` が GHCR へ自動で build & push します。
ビルド時に「ComfyUI に Krea2 のネイティブ対応があるか」「`Krea2EditModelPatch` があるか」を自動チェックし、無い場合はビルドが失敗します（正常な安全装置です）。

## 手順2：RunPod テンプレートを作成（1回だけ）

### 方法A：コンソール（推奨）

RunPod コンソール → **Templates → New Template** に、次の値をそのまま入力します。

| 項目 | 値 |
|---|---|
| Name | `Krea 2 Identity Edit V2 - Image Edit ComfyUI` |
| Template Type | Pod |
| Container Image | `ghcr.io/kyaha909-svg/krea2-edit:latest` |
| Container Start Command | （空欄。イメージ側の ENTRYPOINT が起動します） |
| Container Disk | `40` GB |
| Volume Disk | `50` GB |
| Volume Mount Path | `/workspace` |
| HTTP Ports | `8188, 8888` |
| TCP Ports | `22` |
| Env: `LOWVRAM` | `auto` |
| Env: `COMFY_PORT` | `8188` |

保存すると Template ID が発行されます。以後のデプロイはこのURLがワンクリックになります：

```
https://console.runpod.io/deploy?template=<Template ID>
```

### 方法B：API（任意）

```bash
export RUNPOD_API_KEY=<RunPod Settings → API Keys で発行>
python create_template.py   # Template ID と Deploy URL を表示します
```

APIキーは環境変数でのみ渡します。ファイルやチャットに書かないでください。

## 手順3：Pod をデプロイ

Deploy URL（または Templates → Deploy）を開き、GPU を選んで **Deploy On-Demand**。

- **推奨：VRAM 24GB 級**（RTX 4090 / L4 / L40S / A100 など）。本体13.14GB＋エンコーダー5.24GB＋編集時の活性化で、24GB あると 1024px 編集が安定します
- **最小：VRAM 16GB**。Turbo fp8＋`LOWVRAM=auto`（16GB以下は自動で `--lowvram`）で動作想定です
- 初回はモデルDL（約20.5GB）の時間も課金時間に含まれます

## 手順4：画像編集の使い方

1. Pod が Running になったら **Connect → HTTP Service [Port 8188]** を開く（初回はDL完了まで 502/接続待ちが出ます。Pod の Logs に `[start] Launching ComfyUI` が出れば完了）
2. ComfyUI 左メニュー **Workflow** から `krea2_identity_edit` を開く
3. **Load Image** ノードに人物写真をドラッグ＆ドロップ
4. **Krea2EditGroundedEncode**（positive）の prompt に編集指示を英語で書く。negative 側は空のままにします（通常の CLIPTextEncode は使いません。編集には `Krea2EditModelPatch` と `Krea2EditGroundedEncode` の両方が必須です）
5. **Queue** を押す。結果は `/workspace/output` にも保存されます
6. 生成解像度は **2MP以下**が目安です。既定は 1024×1024 です

プリセット：Identity LoRA（強度 1.0）/ Turbo / **8 steps / CFG 1.0 / euler / simple / denoise 1.0** / ref_boost 2 / ref_boost_a 1 / grounding_px 768 / ref_position = `beside (right of target)` / ref_position_a = `aligned (trained)`。

### 使い方のバリエーション

- **1枚からの再配置（基本形）**：人物写真1枚を入れ、「カフェのテーブルに座らせる」「衣装を赤いレインコートに変える」のように指示します。ref_position = beside により、元の構図に固定されず自由に再配置できます
- **参照2枚の合成（人物をシーンへ）**：グループ2（Second Reference）は初期状態で bypass（無効）です。グループのタイトルバーを右クリックして Bypass を外すと有効になります。**画像1＝シーン**（ref_position_a = aligned / ref_boost_a 1）、**画像2＝人物**（ref_position = beside / ref_boost 2）が V2 の推奨構成です
- **顔を固定したいポートレート**：構図をあまり変えず顔の同一性を強く保ちたい場合は、ref_position を `aligned (trained)` に切り替え、ref_boost は 1〜2 の範囲で調整してください

ブラウザなしの確認用：

```bash
python test_edit.py --url https://<POD_ID>-8188.proxy.runpod.net \
  --image input.jpg --prompt "Change her outfit to a red raincoat, preserving her exact facial identity"
```

## 設定（環境変数）

| 変数 | 既定 | 説明 |
|---|---|---|
| `LOWVRAM` | `auto` | `auto`=VRAM 16GB以下で `--lowvram` 自動付加。`on` / `off` で固定も可 |
| `COMFY_PORT` | `8188` | ComfyUI のポート。通常は変更不要 |
| `HF_TOKEN` | （空） | 不要（全て公開）。設定しても害はありません |

## トラブルシューティング

- **起動直後に 8188 が開かない**：初回は約20.5GBのDL中です。Logs で `[start] downloading:` の進行を確認してください。再起動すると続きから再開します（`wget -c`）
- **編集で OOM**：解像度を 1024 → 768 に下げる／`LOWVRAM=on` を試してください
- **結果が元画像から変わらない・ノイズになる**：CLIPLoader の type が `krea2` か、negative の prompt が空か、LoRA 強度が 1.0 かを確認してください
- **顔が別人になる**：ref_position を aligned に切り替える／ref_boost を 1〜2 で調整する／指示文に `Preserve the exact facial identity` と特徴の説明を足してください

## ライセンス・注意

- Krea 2 本体は **Krea 2 Community License** の対象です。利用前に条件を確認してください
- Identity Edit V2 LoRA は**個人・非商用は無料**、**商用利用には作者のライセンスが別途必要**です
- この編集モデルはコミュニティによる非公式のファインチューンであり、**Krea 公式製品ではありません**
- このテンプレートはあなたの RunPod アカウント内に作るプライベートテンプレートです。公開（Public）にすると他ユーザーも使えますが、イメージ側も公開リポジトリである必要があります
- RunPod のプロキシURLは Pod ID を含むため、共有は控えてください。**Pod を Terminate するとボリュームも消える**プランでは、先に結果をダウンロードしてください（Network Volume を付ければ残ります）

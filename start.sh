#!/usr/bin/env bash
# First boot: download models to the persistent volume (/workspace),
# link them into ComfyUI, then launch ComfyUI on port 8188.
# Later boots: files already exist -> download is skipped, ComfyUI starts fast.
set -euo pipefail

COMFY_DIR="${COMFY_DIR:-/opt/ComfyUI}"
MODELS_DIR="${WORKSPACE_DIR:-/workspace}/models"
PORT="${COMFY_PORT:-8188}"

TURBO_FILE="krea2_turbo_fp8_scaled.safetensors"
TURBO_URL="https://huggingface.co/Comfy-Org/Krea-2/resolve/main/diffusion_models/${TURBO_FILE}"
ENC_FILE="qwen3vl_4b_fp8_scaled.safetensors"
ENC_URL="https://huggingface.co/Comfy-Org/Krea-2/resolve/main/text_encoders/${ENC_FILE}"
VAE_FILE="qwen_image_vae.safetensors"
VAE_URL="https://huggingface.co/Comfy-Org/Krea-2/resolve/main/vae/${VAE_FILE}"
ID_LORA_FILE="krea2_identity_edit_v2.safetensors"
ID_LORA_URL="https://huggingface.co/conradlocke/krea2-identity-edit/resolve/main/${ID_LORA_FILE}"

mkdir -p \
  "$MODELS_DIR/diffusion_models" \
  "$MODELS_DIR/text_encoders" \
  "$MODELS_DIR/vae" \
  "$MODELS_DIR/loras/Krea2" \
  "$COMFY_DIR/user/default/workflows" \
  "$COMFY_DIR/models/loras/Krea2"

AUTH=()
if [ -n "${HF_TOKEN:-}" ]; then AUTH=(-H "Authorization: Bearer ${HF_TOKEN}"); fi

download() { # $1=url  $2=dest — skip when a non-empty file is already there
  if [ -s "$2" ]; then
    echo "[start] already downloaded: $2"
  else
    echo "[start] downloading: $1 -> $2"
    wget -c --tries=5 --timeout=60 "${AUTH[@]}" -O "$2.part" "$1" && mv "$2.part" "$2"
  fi
}

download "$TURBO_URL" "$MODELS_DIR/diffusion_models/$TURBO_FILE"
download "$ENC_URL" "$MODELS_DIR/text_encoders/$ENC_FILE"
download "$VAE_URL" "$MODELS_DIR/vae/$VAE_FILE"
download "$ID_LORA_URL" "$MODELS_DIR/loras/Krea2/$ID_LORA_FILE"

# Link the volume models into ComfyUI's model folders (idempotent)
for sub in diffusion_models text_encoders vae loras; do
  find "$MODELS_DIR/$sub" -type f | while read -r f; do
    rel="${f#$MODELS_DIR/$sub/}"
    mkdir -p "$COMFY_DIR/models/$sub/$(dirname "$rel")"
    ln -sf "$f" "$COMFY_DIR/models/$sub/$rel"
  done
done

# Keep input/output on the volume so results survive a pod restart.
mkdir -p "${WORKSPACE_DIR:-/workspace}/input" "${WORKSPACE_DIR:-/workspace}/output"
for d in input output; do
  if [ -d "$COMFY_DIR/$d" ] && [ ! -L "$COMFY_DIR/$d" ]; then rm -rf "$COMFY_DIR/$d"; fi
  ln -sfn "${WORKSPACE_DIR:-/workspace}/$d" "$COMFY_DIR/$d"
done

# Refresh the bundled workflow (top-level UI json only)
cp -f /opt/workflows/*.json "$COMFY_DIR/user/default/workflows/" 2>/dev/null || true
rm -f "$COMFY_DIR/user/default/workflows/_upstream_krea2_identity_edit.json"

# VRAM flag: auto = --lowvram at <=16 GB VRAM, normal at >16 GB.
EXTRA_ARGS=""
case "${LOWVRAM:-auto}" in
  on|1) EXTRA_ARGS="--lowvram" ;;
  off|0) EXTRA_ARGS="" ;;
  *)
    VRAM_MIB="$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -n1 || echo 0)"
    VRAM_MIB="${VRAM_MIB//[^0-9]/}"
    if [ -n "$VRAM_MIB" ] && [ "$VRAM_MIB" -le 16384 ]; then EXTRA_ARGS="--lowvram"; fi
    echo "[start] GPU VRAM: ${VRAM_MIB:-unknown} MiB (extra args: '${EXTRA_ARGS}')"
    ;;
esac

echo "[start] Launching ComfyUI on port $PORT"
if command -v jupyter >/dev/null 2>&1; then
  nohup jupyter lab --ip=0.0.0.0 --port=8888 --no-browser --allow-root \
    --ServerApp.token='' --ServerApp.password='' \
    --ServerApp.root_dir="${WORKSPACE_DIR:-/workspace}" \
    > /tmp/jupyter.log 2>&1 &
  echo "[start] JupyterLab launching on port 8888"
else
  echo "[start] jupyter not found; skipping JupyterLab"
fi

cd "$COMFY_DIR"
# shellcheck disable=SC2086
exec python main.py --listen 0.0.0.0 --port "$PORT" $EXTRA_ARGS

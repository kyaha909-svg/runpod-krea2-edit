# Krea 2 Edit V2 — Image Edit — RunPod Pod image
# Base: official RunPod PyTorch image (CUDA 12.8 / torch 2.8 / Ubuntu 24.04).
# Models are NOT baked into the image: start.sh downloads them to the
# persistent /workspace volume on first boot (~20.5 GB)
# and reuses them after.
FROM runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    COMFY_DIR=/opt/ComfyUI \
    WORKSPACE_DIR=/workspace \
    LOWVRAM=auto \
    COMFY_PORT=8188

WORKDIR /opt

RUN apt-get update && apt-get install -y --no-install-recommends \
      git wget curl aria2 ffmpeg libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# ComfyUI (latest master — native Krea2 support required) + krea2edit nodes + Manager
RUN git clone --depth 1 https://github.com/comfyanonymous/ComfyUI.git ${COMFY_DIR} \
    && git clone --depth 1 https://github.com/lbouaraba/comfyui-krea2edit.git ${COMFY_DIR}/custom_nodes/comfyui-krea2edit \
    && git clone --depth 1 https://github.com/ltdrdata/ComfyUI-Manager.git ${COMFY_DIR}/custom_nodes/ComfyUI-Manager \
    && pip install -r ${COMFY_DIR}/requirements.txt \
    && pip install jupyterlab huggingface_hub

# Fail the build early if ComfyUI lacks native Krea2 support or the edit nodes are missing
RUN grep -qri "krea2" ${COMFY_DIR}/comfy/ \
    || (echo "ERROR: ComfyUI checkout lacks native Krea2 support — rebuild with a newer ComfyUI" && exit 1)
RUN grep -q "Krea2EditModelPatch" ${COMFY_DIR}/custom_nodes/comfyui-krea2edit/__init__.py \
    && grep -q "Krea2EditGroundedEncode" ${COMFY_DIR}/custom_nodes/comfyui-krea2edit/__init__.py \
    || (echo "ERROR: comfyui-krea2edit nodes missing" && exit 1)

COPY start.sh /start.sh
COPY workflows/ /opt/workflows/
COPY workflows/ ${COMFY_DIR}/user/default/workflows/
RUN chmod +x /start.sh \
    && mkdir -p /workspace

EXPOSE 8188 8888
ENTRYPOINT ["/start.sh"]

"""Generate Krea 2 Edit V2 workflow JSONs (UI format + API format).

UI workflows are transformed copies of the upstream example
(lbouaraba/comfyui-krea2edit workflows/krea2_identity_edit.json, cached at
workflows/_upstream_krea2_identity_edit.json) — node ids/links/groups kept intact.
Key nodes in upstream: KSampler 53, UNETLoader 55, CLIPLoader 56, VAELoader 57,
LoraLoaderModelOnly 71, LoadImage 72, Krea2EditModelPatch 79,
EmptySD3LatentImage 82, ResolutionSelector 83, Krea2EditGroundedEncode 84 (pos) /
85 (neg), second LoadImage 90 (bypassed group 2).

API workflows are hand-built single-image graphs. Node ids:
  1 UNETLoader, 2 CLIPLoader(krea2), 3 VAELoader, 4 LoadImage, 5 VAEEncode,
  6 LoraLoaderModelOnly, 7 EmptySD3LatentImage, 8 Krea2EditModelPatch,
  9 Krea2EditGroundedEncode (positive), 10 Krea2EditGroundedEncode (negative),
  11 KSampler, 12 VAEDecode, 13 SaveImage.
Krea2EditModelPatch INPUT_TYPES (verified from repo __init__.py):
  required: model, source_latent
  optional: source_latent_b, ref_boost, ref_boost_a, fit_mode, ref_boost_mask,
            vae, source_image, source_image_b, target_latent,
            ref_position, ref_position_a
Krea2EditGroundedEncode INPUT_TYPES:
  required: clip, prompt; optional: image, image_b, grounding_px, system_prompt
"""
import copy
import json
import os
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
WF_DIR = os.path.join(HERE, "workflows")
API_DIR = os.path.join(WF_DIR, "api")
os.makedirs(API_DIR, exist_ok=True)
UPSTREAM_URL = "https://raw.githubusercontent.com/lbouaraba/comfyui-krea2edit/main/workflows/krea2_identity_edit.json"
CACHE = os.path.join(WF_DIR, "_upstream_krea2_identity_edit.json")

TURBO = "krea2_turbo_fp8_scaled.safetensors"
IDENTITY_LORA = "Krea2/krea2_identity_edit_v2.safetensors"
ALIGNED = "aligned (trained)"
BESIDE = "beside (right of target)"


def load_upstream():
    if not os.path.exists(CACHE):
        print("downloading upstream workflow ->", CACHE)
        urllib.request.urlretrieve(UPSTREAM_URL, CACHE)
    with open(CACHE) as f:
        return json.load(f)


def node(wf, nid):
    return next(n for n in wf["nodes"] if n["id"] == nid)


def set_notes(wf, mapping):
    for nid, text in mapping.items():
        n = node(wf, nid)
        if n["type"] in ("Note", "MarkdownNote"):
            n["widgets_values"] = [text]


def transform(base, *, lora, unet, steps, cfg, ref_boost, ref_boost_a,
              ref_pos, ref_pos_a, prompt, prefix, wf_id, notes):
    wf = copy.deepcopy(base)
    wf["id"] = wf_id
    node(wf, 55)["widgets_values"][0] = unet
    node(wf, 71)["widgets_values"] = [lora, 1.0]
    ks = node(wf, 53)["widgets_values"]  # [seed, control, steps, cfg, sampler, scheduler, denoise]
    ks[2] = steps
    ks[3] = cfg
    ks[4] = "euler"
    ks[5] = "simple"
    ks[6] = 1.0
    # V2: trailing ref_position / ref_position_a appended
    node(wf, 79)["widgets_values"] = [ref_boost, ref_boost_a, "fit", ref_pos, ref_pos_a]
    node(wf, 84)["widgets_values"] = [prompt, 768, ""]
    node(wf, 85)["widgets_values"] = ["", 768, ""]
    node(wf, 29)["widgets_values"] = [prefix]
    set_notes(wf, notes)
    return wf


IDENTITY_NOTES = {
    100: "Files:\n- krea2_turbo_fp8_scaled\n- qwen3vl_4b_fp8_scaled text encoder, type 'krea2'\n- qwen_image_vae\n- Krea2/krea2_identity_edit_v2.safetensors LoRA (V2, strength 1.0)\nUse this LoRA only, at strength 1.0.",
    101: "YOUR IMAGE - single-ref: the person/scene to restage.\nTwo-image mode (group 2 enabled): THIS slot is the SCENE (image 1),\nthe person goes in group 2 (image 2). Inputs around 1MP; <=2MP total.",
    102: "OPTIONAL second reference - the PERSON for insert-into-scene edits.\nShips DISABLED (purple = bypassed). Enable: right-click this group's\ntitle bar -> toggle Bypass off. Order: scene = image 1, person = image 2.\nTwo-ref preset: scene ref_position_a=aligned / ref_boost_a=1,\nperson ref_position=beside / ref_boost=2.",
    103: "Write the edit in plain English:\n  'Place this person at the cafe table, holding a coffee.'\n  'Change her outfit to a red raincoat.'\nUnique face generic? Append 'Preserve the exact facial identity - ...'.\ngrounding_px 768 (V2). Negative node below: keep prompt empty.",
    104: "FIDELITY: ref_boost = 2 (V2 Identity restage preset), ref_boost_a = 1.\nref_position = beside (right of target) - freer restaging;\nref_position_a = aligned (trained) for the scene in two-ref mode.\nfit_mode = fit.",
    105: "Turbo model: 8 steps, cfg 1.0, euler / simple, denoise 1.0 (V2 preset).",
    106: "KREA 2 IDENTITY EDIT - V2\nUse an image like a LoRA: reference in, plain-English instruction, Queue.\n1) load image in group 1  2) write instruction in group 3  3) Queue.\nTwo-image composite: enable group 2. Requires comfyui-krea2edit >= 2.0.0.\ngithub.com/lbouaraba/comfyui-krea2edit - huggingface.co/conradlocke/krea2-identity-edit",
    107: "Output resolution. 1024x1024 default; stay at <=2MP.",
}


def api_workflow(*, lora, steps, cfg, ref_boost, ref_boost_a, ref_pos, ref_pos_a, prompt, prefix):
    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": TURBO, "weight_dtype": "default"}, "_meta": {"title": "UNETLoader - Krea2 Turbo fp8"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_4b_fp8_scaled.safetensors", "type": "krea2", "device": "default"}, "_meta": {"title": "CLIPLoader - Qwen3VL 4B (type krea2)"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "qwen_image_vae.safetensors"}, "_meta": {"title": "VAELoader"}},
        "4": {"class_type": "LoadImage", "inputs": {"image": "example.png"}, "_meta": {"title": "LoadImage - source"}},
        "5": {"class_type": "VAEEncode", "inputs": {"pixels": ["4", 0], "vae": ["3", 0]}, "_meta": {"title": "VAEEncode - source latent"}},
        "6": {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["1", 0], "lora_name": lora, "strength_model": 1.0}, "_meta": {"title": "LoRA - edit V2 (1.0, one only)"}},
        "7": {"class_type": "EmptySD3LatentImage", "inputs": {"width": 1024, "height": 1024, "batch_size": 1}, "_meta": {"title": "EmptySD3LatentImage 1024x1024"}},
        "8": {"class_type": "Krea2EditModelPatch", "inputs": {"model": ["6", 0], "source_latent": ["5", 0], "vae": ["3", 0], "source_image": ["4", 0], "target_latent": ["7", 0], "ref_boost": ref_boost, "ref_boost_a": ref_boost_a, "fit_mode": "fit", "ref_position": ref_pos, "ref_position_a": ref_pos_a}, "_meta": {"title": "Krea2EditModelPatch"}},
        "9": {"class_type": "Krea2EditGroundedEncode", "inputs": {"clip": ["2", 0], "prompt": prompt, "image": ["4", 0], "grounding_px": 768}, "_meta": {"title": "GroundedEncode - positive"}},
        "10": {"class_type": "Krea2EditGroundedEncode", "inputs": {"clip": ["2", 0], "prompt": "", "image": ["4", 0], "grounding_px": 768}, "_meta": {"title": "GroundedEncode - negative (empty)"}},
        "11": {"class_type": "KSampler", "inputs": {"model": ["8", 0], "positive": ["9", 0], "negative": ["10", 0], "latent_image": ["7", 0], "seed": 42, "steps": steps, "cfg": cfg, "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}, "_meta": {"title": "KSampler"}},
        "12": {"class_type": "VAEDecode", "inputs": {"samples": ["11", 0], "vae": ["3", 0]}, "_meta": {"title": "VAEDecode"}},
        "13": {"class_type": "SaveImage", "inputs": {"images": ["12", 0], "filename_prefix": prefix}, "_meta": {"title": "SaveImage"}},
    }


def check_ui(wf):
    node_ids = {n["id"] for n in wf["nodes"]}
    link_ids = set()
    for lid, o, _os, t, _ts, _ty in wf["links"]:
        assert o in node_ids and t in node_ids, f"link {lid} -> missing node"
        link_ids.add(lid)
    for n in wf["nodes"]:
        for inp in n.get("inputs", []) or []:
            if inp.get("link") is not None:
                assert inp["link"] in link_ids, f"node {n['id']} input link {inp['link']} missing"
        for out in n.get("outputs", []) or []:
            for l in out.get("links") or []:
                assert l in link_ids, f"node {n['id']} output link {l} missing"
    # reverse: every link referenced by at least one node endpoint
    referenced = set()
    for n in wf["nodes"]:
        for inp in n.get("inputs", []) or []:
            if inp.get("link") is not None:
                referenced.add(inp["link"])
        for out in n.get("outputs", []) or []:
            referenced.update(out.get("links") or [])
    assert link_ids <= referenced, f"orphan links: {link_ids - referenced}"


def main():
    base = load_upstream()
    identity_prompt = "Change her outfit to a red raincoat, preserving her exact facial identity."
    files = {
        os.path.join(WF_DIR, "krea2_identity_edit.json"): transform(
            base, lora=IDENTITY_LORA, unet=TURBO, steps=8, cfg=1.0, ref_boost=2, ref_boost_a=1,
            ref_pos=BESIDE, ref_pos_a=ALIGNED, prompt=identity_prompt,
            prefix="krea2_identity_edit", wf_id="krea2-identity-edit-v2", notes=IDENTITY_NOTES),
        os.path.join(API_DIR, "krea2_identity_edit_api.json"): api_workflow(
            lora=IDENTITY_LORA, steps=8, cfg=1.0, ref_boost=2, ref_boost_a=1,
            ref_pos=BESIDE, ref_pos_a=ALIGNED, prompt=identity_prompt, prefix="krea2_identity_edit"),
    }
    for path, data in files.items():
        if "/api/" not in path.replace(os.sep, "/"):
            check_ui(data)
        with open(path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print("wrote", path)


if __name__ == "__main__":
    main()

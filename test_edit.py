"""Headless Krea 2 Identity Edit against a running pod (no browser needed).

Usage:
  python test_edit.py --url https://POD_ID-8188.proxy.runpod.net --image input.jpg --prompt "..."
  optional: --seed 42

API workflow node ids (workflows/api/krea2_identity_edit_api.json):
  4 = LoadImage, 9 = Krea2EditGroundedEncode (positive prompt),
  11 = KSampler (seed), 13 = SaveImage (output).
Uploads the image, posts the API workflow to ComfyUI /prompt, waits,
and downloads the result next to this script.
"""
import argparse
import json
import os
import time
import urllib.parse
import urllib.request
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))


def post_json(url, payload):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read())


def upload(base, path):
    boundary = uuid.uuid4().hex
    with open(path, "rb") as f:
        blob = f.read()
    name = os.path.basename(path)
    head = (
        "--" + boundary + "\r\n"
        + 'Content-Disposition: form-data; name="image"; filename="' + name + '"\r\n'
        + "Content-Type: application/octet-stream\r\n\r\n"
    ).encode()
    body = head + blob + ("\r\n--" + boundary + "--\r\n").encode()
    req = urllib.request.Request(
        base + "/upload/image", data=body,
        headers={"Content-Type": "multipart/form-data; boundary=" + boundary})
    return json.loads(urllib.request.urlopen(req).read())["name"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True, help="ComfyUI base URL of the pod")
    ap.add_argument("--image", required=True)
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    base = args.url.rstrip("/")

    with open(os.path.join(HERE, "workflows", "api", "krea2_identity_edit_api.json")) as f:
        wf = json.load(f)

    wf["4"]["inputs"]["image"] = upload(base, args.image)
    wf["9"]["inputs"]["prompt"] = args.prompt
    wf["11"]["inputs"]["seed"] = args.seed

    prompt_id = post_json(base + "/prompt", {"prompt": wf})["prompt_id"]
    print("queued:", prompt_id)
    while True:
        time.sleep(3)
        with urllib.request.urlopen(base + "/history/" + prompt_id) as r:
            hist = json.loads(r.read())
        if prompt_id in hist:
            outputs = hist[prompt_id]["outputs"]["13"]["images"]
            break
    for img in outputs:
        q = urllib.parse.urlencode(
            {"filename": img["filename"], "subfolder": img.get("subfolder", ""),
             "type": img.get("type", "output")})
        out = os.path.join(HERE, "result_" + img["filename"])
        with urllib.request.urlopen(base + "/view?" + q) as r, open(out, "wb") as f:
            f.write(r.read())
        print("saved:", out)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""wangliupu 双人换人：构建 rv2v 单段工作流并提交。
参考图 <Picture 1> = 慕沛灵（女），<Picture 2> = 韩立（男）。
画布 768x576（4:3，与源片同比例），24fps，4 步 turbo LoRA，refine 二采，静音无音轨。
"""
import copy
import json
import os
import sys

sys.path.insert(0, r"E:\VideoShotSplitter\vogue768")
import vogue768_batch as B

BASE = r"E:\VideoShotSplitter\wangliupu"
TEMPLATE = r"E:\VideoShotSplitter\vogue\h3_template.json"
SRC = os.environ.get("WLP_SRC", "wangliupu_src24.mp4")
REF1 = "wlp_ref_female.png"     # 慕沛灵
REF2 = "wlp_ref_male.png"       # 韩立

W = int(os.environ.get("WLP_W", "768"))
H = int(os.environ.get("WLP_H", "576"))
FPS = 24
TOTAL = int(os.environ.get("WLP_FRAMES", "413"))
SEED = int(os.environ.get("WLP_SEED", "9783"))
SEG_LENGTHS = [int(x) for x in os.environ.get("WLP_SEGS", "").replace(" ", "").split(",") if x] or [TOTAL]

PROMPT_DRAFT = os.path.join(BASE, "wlp_prompt.txt")
FOUR_VIEW_RULE = os.path.join(BASE, "wlp_fourview.txt")


def load_prompt():
    draft = open(PROMPT_DRAFT, encoding="utf-8").read().strip()
    rule = open(FOUR_VIEW_RULE, encoding="utf-8").read().strip()
    assert "{{FOUR_VIEW_RULE}}" in draft, "占位符丢失"
    p = draft.replace("{{FOUR_VIEW_RULE}}", rule)
    for k in ("LOCKED HARD RULE", "[A] CLOSE-UP", "[B] ALL REMAINING FULL-BODY",
              "COSTUME OVERRIDE", "REFERENCE SHEET ALWAYS WINS", "PANEL SEPARATION",
              "camera_composition_lock", "two_subject_lock", "tail_frame_fidelity"):
        assert k in p, "规则缺失: " + k
    assert "{{FOUR_VIEW_RULE}}" not in p
    return p


def patch_video(v, filename, total):
    v["fileName"] = filename
    v["videoFile"] = filename
    v["subfolder"] = ""
    v["type"] = "input"
    v["nativeFps"] = FPS
    v["nativeFrameCount"] = total
    v["sourceFrameCount"] = total
    v["duration"] = round(total / FPS, 6)
    v["storageWidth"], v["storageHeight"] = W, H
    v["frames"] = []
    v["frameMap"] = []
    v["deletedSourceRanges"] = []


def build(tpl, prompt):
    api = copy.deepcopy(tpl)
    p = api["prompt"]
    t = json.loads(p["37"]["inputs"]["timeline_data"])

    t["totalFrames"] = TOTAL
    t["frameRate"] = FPS
    t["width"], t["height"] = W, H
    t["refMaxSize"] = max(W, H)
    t["editMode"] = "segment"
    t["runSelectEnabled"] = False
    t["runSelection"] = []
    patch_video(t["video"], SRC, TOTAL)
    for c in t.get("videoClips") or []:
        patch_video(c, SRC, TOTAL)

    refs = [
        {"imageFile": REF1, "fileName": "", "type": "input", "subfolder": "", "index": 0},
        {"imageFile": REF2, "fileName": "", "type": "input", "subfolder": "", "index": 1},
    ]
    t["global"]["refs"] = copy.deepcopy(refs)
    t["global"]["sourceWidth"], t["global"]["sourceHeight"] = W, H
    t["global"]["commonEnabled"] = False

    o = t["output"]
    o["mode"] = "long_edge"
    o["megapixels"] = 1.0
    o["multiple"] = 32
    o["longEdge"] = max(W, H)
    o["width"], o["height"] = W, H
    o["audioMode"] = "mute"
    o["exportMode"] = os.environ.get("WLP_EXPORT", "all")
    CONT = os.environ.get("WLP_CONT", "0") == "1"
    o["continuityEnabled"] = CONT
    o["continuityOverlapFrames"] = int(os.environ.get("WLP_CONT_OVL", "22")) if CONT else 0
    o["continuityKeepTail"] = False
    o["maxExportFrames"] = 0

    segs = []
    cursor = int(os.environ.get("WLP_START", "0"))
    for si, ln in enumerate(SEG_LENGTHS):
        seg = copy.deepcopy(t["segments"][0])
        seg.update({
            "id": "wlp_s%d" % si,
            "start": cursor,
            "length": ln,
            "frameCount": ln,
            "durationSec": round(ln / FPS, 3),
            "_videoFrameCount": ln,
            "prompt": prompt,
            "negativePrompt": "",
            "taskType": "rv2v — 参考素材改视频(Reference Video Edit)",
            "refs": copy.deepcopy(refs),
            "refImageSize": "match",
            "refAudios": [],
            "refVideos": [],
            "referenceVideo": {"videoFile": "", "fileName": "", "type": "input", "subfolder": ""},
            "genImage": {"imageFile": "", "fileName": ""},
        })
        segs.append(seg)
        cursor += ln
    t["segments"] = segs

    ws = t.get("videoWorkspaces", {}).get("rv2v")
    if isinstance(ws, dict) and isinstance(ws.get("video"), dict):
        patch_video(ws["video"], SRC, TOTAL)
        for c in ws.get("videoClips") or []:
            patch_video(c, SRC, TOTAL)
        ws["totalFrames"] = TOTAL
        ws["frameRate"] = FPS
        ws["storageWidth"], ws["storageHeight"] = W, H
        ws["currentFrame"] = 0
        ws["runSelectEnabled"] = False
        ws["runSelection"] = []
        ws["segments"] = copy.deepcopy(t["segments"])

    n37 = p["37"]["inputs"]
    n37["timeline_data"] = json.dumps(t, ensure_ascii=False, separators=(",", ":"))
    n37["frame_rate"] = FPS
    n37["total_frames"] = TOTAL
    n37["width"], n37["height"] = W, H
    n37["ref_max_size"] = max(W, H)
    n37["steps"] = int(os.environ.get("WLP_STEPS", "4"))
    n37["cfg"] = 1.0
    n37["sampler"] = "res_multistep"
    n37["scheduler"] = "simple"
    n37["shift_video"] = 12
    n37["shift_audio"] = 3
    n37["seed"] = SEED
    n37["clear_vram_between_segments"] = True
    n37["clear_vram_before_refine"] = True
    if "task_type" in n37:
        n37["task_type"] = "rv2v — 参考素材改视频(Reference Video Edit)"

    if os.environ.get("WLP_NOREFINE", "0") == "1":
        # 彻底断开 refine：不给节点 37 传 refine 输入，节点 44/45 自然不执行
        api["prompt"].pop("44", None)
        api["prompt"].pop("45", None)
        p["37"]["inputs"].pop("refine", None)

    assert p["24"]["inputs"].get("lora_name", "").startswith(
        "minimax_h3_ref2v_lightx2v_turbo_4step"), "4 步 turbo LoRA 丢失"

    if "44" in p:
        n44 = p["44"]["inputs"]
        n44["mode"] = "latent_upscale" if os.environ.get("WLP_NOREFINE", "0") == "1" else "refine"
        n44["upscale_method"] = "h3_latent"
        n44["megapixels"] = 1.0
        n44["width"], n44["height"] = W, H
        n44["aspect_ratio"] = "跟随导演台"
        n44["skip_fl2v"] = True
        n44["confirm_first_pass"] = False
        n44["enable_latent_chunking"] = os.environ.get("WLP_CHUNK", "0") == "1"
        n44["enable_tiling"] = os.environ.get("WLP_TILING", "1") == "1"
        n44["tile_count"] = int(os.environ.get("WLP_TILES", "2"))
        n44["tile_overlap"] = int(os.environ.get("WLP_OVERLAP", "128"))
        p["45"]["inputs"]["steps"] = int(os.environ.get("WLP_STEPS", "4"))
        p["45"]["inputs"]["scheduler"] = "simple"

    p["21"]["inputs"] = {"images": ["37", 0], "fps": FPS, "bit_depth": 8,
                         "color_space": "sRGB", "codec": "none"}
    p["5"]["inputs"]["filename_prefix"] = "video/" + os.environ.get("WLP_PREFIX", "wlp_s0")
    api["client_id"] = "wlp-s0"
    return api


def main():
    override = os.environ.get("WLP_PROMPT", "").strip()
    prompt = open(override, encoding="utf-8").read().strip() if override else load_prompt()
    tpl = json.load(open(TEMPLATE, encoding="utf-8"))
    api = build(tpl, prompt)
    os.makedirs(BASE, exist_ok=True)
    wfp = os.path.join(BASE, "wf_wlp_s0.json")
    json.dump(api, open(wfp, "w", encoding="utf-8"), ensure_ascii=False)
    print("WF " + wfp)
    print("frames=%d %dx%d fps=%d refs=%d segs=%s" % (TOTAL, W, H, FPS, 2, SEG_LENGTHS or "single"), flush=True)
    import subprocess as _sp
    import time as _t
    import urllib.request as _ur

    def _api_ok():
        try:
            with _ur.urlopen("http://127.0.0.1:8188/system_stats", timeout=5) as _r:
                return _r.status == 200
        except Exception:
            return False

    if not _api_ok():
        print("COMFY_DOWN -> clean_start")
        _sp.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                 r"E:\VideoShotSplitter\wangliupu\clean_start.ps1"], capture_output=True)
        for _ in range(40):
            if _api_ok():
                break
            _t.sleep(3)
        print("COMFY_UP" if _api_ok() else "COMFY_NOT_READY")
        return 4
    B.clear_cache()
    pid = B.submit(wfp)
    print("PID " + pid, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

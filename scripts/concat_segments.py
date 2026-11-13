#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把分段导出的 seg_XXXX.mp4 拼成整片并探规格。"""
import os
import subprocess
import sys

FF = r"E:\Tools\ffmpeg\bin\ffmpeg.exe"
FP = r"E:\Tools\ffmpeg\bin\ffprobe.exe"
src_dir = sys.argv[1]
out = sys.argv[2]
os.makedirs(os.path.dirname(out), exist_ok=True)

files = sorted([f for f in os.listdir(src_dir) if f.startswith("seg_") and f.endswith(".mp4")
                and "_pre" not in f and "_face" not in f])
if not files:
    print("NO_SEGMENTS in " + src_dir)
    sys.exit(1)
print("segments=%d" % len(files))

lst = os.path.join(os.path.dirname(out), "filelist.txt")
with open(lst, "w", encoding="utf-8") as f:
    for name in files:
        f.write("file '%s'\n" % os.path.join(src_dir, name).replace("\\", "/"))

subprocess.check_call([FF, "-y", "-v", "error", "-f", "concat", "-safe", "0",
                       "-i", lst, "-c", "copy", out])
info = subprocess.check_output([FP, "-v", "error", "-select_streams", "v:0", "-count_frames",
                                "-show_entries", "stream=width,height,r_frame_rate,nb_read_frames",
                                "-show_entries", "format=duration,size",
                                "-of", "default=nw=1", out]).decode()
print(info.strip())
audio = subprocess.check_output([FP, "-v", "error", "-select_streams", "a", "-show_entries",
                                 "stream=codec_name", "-of", "default=nw=1", out]).decode().strip()
print("audio_streams=" + (audio if audio else "NONE"))
print("OUT " + out)

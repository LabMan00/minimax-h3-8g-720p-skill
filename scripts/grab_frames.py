#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按帧号抽帧：seam_check.py <mp4> <outdir> <f1,f2,...>"""
import os
import subprocess
import sys

FF = r"E:\Tools\ffmpeg\bin\ffmpeg.exe"
FP = r"E:\Tools\ffmpeg\bin\ffprobe.exe"
src, out, frames = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(out, exist_ok=True)
info = subprocess.check_output([FP, "-v", "error", "-select_streams", "v:0", "-count_frames",
                                "-show_entries", "stream=width,height,r_frame_rate,nb_read_frames",
                                "-show_entries", "format=duration", "-of", "default=nw=1", src]).decode()
print(info.strip())
FPS = 24
for fr in [int(x) for x in frames.replace(" ", "").split(",") if x]:
    p = os.path.join(out, "f%04d.png" % fr)
    subprocess.check_call([FF, "-y", "-v", "error", "-ss", "%.4f" % (fr / FPS), "-i", src,
                           "-frames:v", "1", p])
    print("WROTE f%04d.png" % fr)

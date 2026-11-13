# Win 环境与命令

## 主机与凭据

| 项 | 值 |
|---|---|
| 主机 | `labman00@192.168.10.75`（局域网，Win 11，RTX 4060 Laptop 8 GB / 15.2 GB RAM） |
| SSH 密钥 | `/Users/mac/.workbuddy/keys/workbuddy_win` |
| ComfyUI | `http://127.0.0.1:8188`（Win 本机回环，从 Mac 走 ssh 转发或远程执行 curl） |
| 程序目录 | `E:\ComfyUI` |
| 业务工作目录 | `E:\VideoShotSplitter\wangliupu`（本流水线的脚本与产物） |
| 分段导出目录 | `E:\ComfyUI\output\minimax_seg_export\<时间戳>\` |
| 输入素材 | `E:\ComfyUI\input\` |
| 批量工具目录 | `E:\VideoShotSplitter\vogue768\`（含 `watch_job.py`、`verify_submit.py`） |

ssh 调用统一加：

```bash
ssh -i /Users/mac/.workbuddy/keys/workbuddy_win \
    -o StrictHostKeyChecking=no -o ConnectTimeout=10 -o BatchMode=yes \
    labman00@192.168.10.75 "<命令>"
```

Windows 上跑 PowerShell 脚本务必用 `-NoProfile -ExecutionPolicy Bypass -File`，命令里带中文或 `|`、`*` 时**写成 .ps1 文件再执行**，直接 `-Command` 极容易出现编码/引号解析错误（踩过多次）。

## 启动 ComfyUI（唯一正确姿势）

```powershell
# 杀掉所有 main.py 实例，然后用带 --disable-comfy-compiler 的参数重启
powershell -NoProfile -ExecutionPolicy Bypass -File E:\VideoShotSplitter\wangliupu\clean_start.ps1
```

脚本行为：清残留实例 → `Win32_Process.Create` 拉起 → 轮询 `/system_stats` 返回 200 → 打印 `API_UP`。

启动参数（缺一不可）：

```
main.py --listen 127.0.0.1 --port 8188 --enable-manager --use-sage-attention
        --disable-pinned-memory --disable-comfy-compiler
```

- `--disable-comfy-compiler`：避开 `comfy_aimdo malloc_graph → stack overflow` 的原生崩溃
- `--disable-pinned-memory`：8 GB 卡上减少锁页占用

旧脚本 `E:\VideoShotSplitter\vogue768\launch_comfyui_768.ps1` **不带** `--disable-comfy-compiler`，不要在关键任务前用它拉起服务。

## 源片重采样

把原始素材转成目标画布、24 fps、指定帧数、去音轨：

```bat
E:\Tools\ffmpeg\bin\ffmpeg.exe -y -v error -i <原始文件> ^
  -vf scale=1152:864:flags=lanczos,fps=24 -frames:v 413 -an ^
  -c:v libx264 -crf 16 -preset medium -pix_fmt yuv420p ^
  E:\ComfyUI\input\<ascii_name>.mp4
```

- 画幅保持源片比例（4:3 素材 → 1152×864）；H3 画布宽高必须能被 32 整除
- 帧数取 `17k+5`：413 / 396 / 379 / 362 / 345 …
- 常见坑：源片 960×720 → 直接用 `fit_canvas` 塞进 9:16 会居中裁掉左右约 28%，双人构图直接废；必须按源比例出画布

## 提交任务

```bat
cmd /c "set WLP_W=1152&& set WLP_H=864&& set WLP_FRAMES=413&& ^
 set WLP_SEGS=51,51,51,51,51,51,51,56&& set WLP_CONT=1&& set WLP_CONT_OVL=5&& ^
 set WLP_NOREFINE=0&& set WLP_TILING=0&& set WLP_EXPORT=segments&& ^
 set WLP_SEED=9783&& set WLP_PREFIX=wlp_final&& set WLP_SRC=wangliupu_src24_hi.mp4&& ^
 set WLP_PROMPT=E:\VideoShotSplitter\wangliupu\wlp_prompt_v2.txt&& ^
 cd /d E:\VideoShotSplitter\wangliupu && E:\ComfyUI\venv\Scripts\python.exe wlp_build.py"
```

成功输出 `WF ...json`、`frames=... segs=[...]`、`PID <prompt_id>`。

## 监控

两种方式：

1. `E:\ComfyUI\venv\Scripts\python.exe E:\VideoShotSplitter\vogue768\watch_job.py <prompt_id> 7200` —— 每 30 秒打印 GPU/队列/日志尾，任务结束自动退出
2. 直接读内存日志（最可靠，不受日志文件重定向影响）：

```bash
ssh ... 'curl -s "http://127.0.0.1:8188/internal/logs/raw"'
```

关注的日志行：
- `MiniMax H3 Director segment N/M done (X frames, task=rv2v)`
- `Director continuity: pinned N video frames (latent), audio off`
- `Director refine pass 1/1 (sigmas wired euler 4-step)`
- `Segment N refine failed (...)` ← 出现即代表二采被跳过
- `100%|...| 4/4 [05:03<00:00, 75.76s/it]` ← 单段采样耗时

## 中断

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8188/interrupt
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8188/queue `
  -Body (ConvertTo-Json @{clear=$true}) -ContentType application/json
```

`interrupt` 只在采样步边界生效，单步几百秒时可能要等 1–3 分钟才真的停；反复确认 `queue_running` 归零后再提交新任务。

# 二采、导出与拼接

## 一、二采（refine）的四个坑

MiniMax H3 Director 的二采由节点 44 `MiniMaxH3DirectorRefine` 控制，node 37 的 `refine` 输入接收它的输出。踩过的坑：

| 配置 | 现象 | 结论 |
|---|---|---|
| `mode=refine`，`enable_tiling=true`，`tile_count=3`，`tile_overlap=64` | 画面出现**同一个人物横向三连影 + 马赛克**，整片报废 | 分块边界在潜变量宽度上取整算不齐，禁用 |
| `mode=refine`，`tile_count=2`，`tile_overlap=128` | 日志 `The size of tensor a (7) must match the size of tensor b (6) at non-singleton dimension 4`，随后 `keeping first-pass latent` | 干净回退，等于**没跑二采** |
| `mode=latent_upscale`（想用它「关」二采） | `H3 latent upscale is enlarge-only (got 1152×864 → 960×704)`，残留 latent 与首采混合 → **半透明叠影** | 假关闭，禁止使用 |
| `mode=refine`，`enable_tiling=false`（整帧二采） | 51 帧实测：二采 4 步 57.5 秒/步，单段多约 4 分钟，无 OOM，画面最干净 | **当前推荐** |
| 硬断开（`prompt["37"]["inputs"].pop("refine")` 并移除节点 44/45） | 完全不跑二采，无叠影 | 不需要二采时的干净做法 |

判断二采是否真的生效，**只能靠像素**：日志里 `Director refine pass 1/1` 出现并不代表成功，必须确认之后没有 `refine failed`，并且抽帧看不出叠影/重影。

## 二、分段导出（必须）

`exportMode=all` 在 1152×864 × 413 帧会失败：

```
RuntimeError: not enough memory: you tried to allocate 4932845568 bytes
  at lib/image_prep.py:152 cat_frames_variable_size → torch.cat(clips, dim=0)
```

原因：413 × 1152 × 864 × 3 通道 × float32 ≈ **4.93 GB 连续内存**，机器只有 15.2 GB 且已被模型占满。

改用：

```
WLP_EXPORT=segments
```

行为：逐段写 mp4 后立即释放该段像素，不做整片拼接。产物：

```
E:\ComfyUI\output\minimax_seg_export\<时间戳>\seg_0000.mp4      # 二采成片
                                           seg_0000_pre.mp4   # 一采对照
```

## 三、ffmpeg 拼接

```bash
E:\ComfyUI\venv\Scripts\python.exe E:\VideoShotSplitter\wangliupu\concat_seg.py \
    <分段目录> <输出 mp4>
```

脚本逻辑（等价于手工命令）：

1. 按文件名排序收集 `seg_XXXX.mp4`，排除 `_pre` / `_face`
2. 写 `filelist.txt`（每行 `file '<绝对路径>'`，路径用 `/`）
3. `ffmpeg -f concat -safe 0 -i filelist.txt -c copy out.mp4`
4. 用 ffprobe 输出 `width/height/r_frame_rate/nb_read_frames/duration/size` 与音频流情况

注意：
- `-c copy` 要求所有分段编码参数一致（同一批任务生成的天然一致）
- 拼接前先确认分段数量与规划一致（例：8 段），少一段就会静默变短
- 拼接后用 `nb_read_frames` 核对总帧数（例：413）

## 四、抽帧核对

```bash
E:\ComfyUI\venv\Scripts\python.exe E:\VideoShotSplitter\wangliupu\seam2.py \
    <mp4> <输出目录> 0,100,200,300,412
```

按帧号取帧（内部按 `帧号/24` 秒 seek），输出 `f0000.png …`。段缝检查取 `段边界-1` 与 `段边界` 两帧。

## 五、交付

- 本地交付目录：`/Users/mac/WorkBuddy/Claw/_deliver/wangliupu/`
- 命名：`wangliupu_swap_1152x864.mp4`、`wangliupu_swap_768x576.mp4` 这类「主体_方式_规格」格式
- 局域网页面（可选）：`/Users/mac/WorkBuddy/Claw/wlp_lan/serve.py`，端口 8766，`python3 serve.py --daemon` 启动；页面每 5 秒拉 `/api/state`，出片后自动 scp 回来并挂 `<video>`
- 页面数据源是 Win 端 `snapshot.ps1`（见 `scripts/win_status_probe.ps1`），其中 `$prefix` 必须改成当前任务的输出前缀，否则页面显示的永远是上一个任务

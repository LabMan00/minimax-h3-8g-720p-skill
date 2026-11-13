# minimax-h3-8g-720p-skill

在 **RTX 4060 Laptop 8 GB 显存 / 15.2 GB 内存** 这种消费级小显存机器上，用 ComfyUI 的 MiniMax H3 Director（rv2v / 视频编辑）做**换人视频**的完整可复现方案：把源视频里的真人换成参考图角色，同时保住原片的动作、构图、机位与背景，稳定产出 720p 级（1152×864）成片。

这个仓库不是"跑通一次"的记录，而是**踩完坑之后剩下的可用路径**：每条参数上限都是实测数字，每个坑都写清了失败现象与处置方式。

## 能力范围

- 单人换人、双人同时换人（四视图参考图，按 `<Picture 1>` / `<Picture 2>` 绑定）
- 长片分段生成 + 段间融合 + 可选二采精修
- 分段导出 + ffmpeg 无损拼接，规避整片拼接的内存墙
- 输出等长（帧数与源片一致）、静音无音轨
- 抽帧验收流程，防止"日志成功但画面报废"

## 快速开始

1. 把 `scripts/` 里的脚本放到 Win 的业务目录（示例：`E:\VideoShotSplitter\wangliupu\`）
2. 用 `win_clean_start.ps1` 启动 ComfyUI（必须带 `--disable-comfy-compiler`）
3. 用 `build_h3_swap.py` 提交任务，参数全部走环境变量：

```bat
set WLP_W=1152&& set WLP_H=864&& set WLP_FRAMES=413&& ^
set WLP_SEGS=51,51,51,51,51,51,51,56&& set WLP_CONT=1&& set WLP_CONT_OVL=5&& ^
set WLP_NOREFINE=0&& set WLP_TILING=0&& set WLP_EXPORT=segments&& ^
set WLP_SEED=9783&& set WLP_PREFIX=myjob&& set WLP_SRC=src24.mp4&& ^
set WLP_PROMPT=prompt.txt&& E:\ComfyUI\venv\Scripts\python.exe build_h3_swap.py
```

4. 出片后用 `concat_segments.py` 拼接，`grab_frames.py` 抽帧验收

详细参数见 `references/`。

## 实测数据：显存拐点在 56 帧

1152×864，4 步 turbo LoRA，单段「有效生成帧数」与耗时的关系：

| 有效帧 | 配置示例 | 每步耗时 | 判定 |
|---|---|---|---|
| 22 | 22 帧首段 | 40.7 s | 可用 |
| **56** | 56 无融合 / 51+5 / 34+22 | **44–90 s** | **黄金档** |
| 61 | 56 体 + 5 融合 | 172 s | 掉进换页区 |
| 72 | 72 无融合 | 305 s | 不可用 |
| 78 | 56 体 + 22 融合 | 首步 >17 min | 不可用 |
| 107 | 107 无融合 | 744 s | 不可用 |

关键不是线性变慢，而是显存顶到 7.8 GB 后开始反复换页。所以**想加融合改善接缝，只能缩短段长换预算**，不能硬堆融合帧数。

## 五个花钱买来的坑

**1. 提示词过长会把换人效果压没**
15,265 字符的四视图长文 → 两人都没换，模型退化成照着源片重绘；压到 1,091 字符并写出具体服装配置（配色/领型/袖型/长度/鞋/发型）→ 稳定换人。有效区间 900–1400 字符。

**2. refine 开空间 tiling 会拼出三连影**
`tile_count=3` → 同一个人物横向三重影 + 马赛克，整片报废；`tile_count=2` → 尺寸错配静默回退（等于没跑二采）；`mode=latent_upscale` 想"假关闭" → 残留 latent 混出半透明叠影。**唯一可用的是整帧二采（关 tiling）**，51 帧实测 57.5 秒/步、单段多约 4 分钟。

**3. 整片拼接会撞内存墙**
`exportMode=all` 在 413 帧 × 1152×864 需要一次性分配 4.93 GB 连续内存（float32 帧拼接），机器内存不够直接抛 `not enough memory at cat_frames_variable_size`。必须 `exportMode=segments` + ffmpeg `-c copy` 拼接。

**4. 融合帧数只有 5/22/39/56 四档**
填 8 会被吸附成 5；且参考核帧上限是 2 帧，所以 5 帧融合的前文只有 0.2 秒，实际收益很弱，22 帧（0.92 秒）才有意义。

**5. 只读日志判断成功会放过废片**
曾经 8/8 段全绿、refine 无报错、文件体积翻倍，实际每帧都是三重影。**验收必须抽帧看像素**，这条已写成强制门槛。

## 目录结构

```
SKILL.md                             主流程、硬性前提、速查表、故障表
references/
  win-environment.md                 主机/路径/启动参数/提交/监控/中断
  params-and-limits.md               实测矩阵、融合档位、段长规划算法
  prompt-playbook.md                 四视图分工、1091 字模板、长度阈值
  refine-export-concat.md            二采四个坑、分段导出、ffmpeg 拼接
  verification-delivery.md           必查帧位、检查清单、汇报模板
scripts/
  build_h3_swap.py                   多段构建 + 提交
  concat_segments.py                 分段无损拼接 + 规格探测
  grab_frames.py                     按帧号抽帧
  win_clean_start.ps1                清实例 + 正确参数启动 ComfyUI
  win_status_probe.ps1               队列/段进度/GPU/产物快照
```

## 硬件前提

- GPU：8 GB 显存（RTX 4060 Laptop 实测）
- 内存：≥15 GB（权重约 26 GB，靠显存与内存来回搬）
- 磁盘：模型与中间产物建议 ≥100 GB 空闲
- 软件：ComfyUI + MiniMax H3 权重 + lightx2v 4 步 turbo LoRA + ffmpeg

显存更小（<8 GB）不建议；显存 ≥16 GB 时可以把段长提到 73+ 并用 22 帧融合，成本会低很多。

## License

MIT

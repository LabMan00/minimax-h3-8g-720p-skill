---
name: h3-character-swap
description: This skill should be used when generating MiniMax H3 (rv2v / 视频编辑) character-replacement videos with ComfyUI on the Windows GPU box — planning segments, picking resolution and continuity overlap, writing identity prompts from four-view character sheets, avoiding VRAM cliffs, running the refine pass, exporting and verifying the final clip. Trigger on requests such as 换人视频、rv2v、参考图换人、MiniMax H3 视频编辑、动作保持换人.
agent_created: true
---

# MiniMax H3 换人视频（ComfyUI / Win 8G 卡）

## 用途

在一台 8 GB 显存 + 15.2 GB 内存的 Windows 机上，用 ComfyUI 的 MiniMax H3 Director（rv2v / 视频编辑）把源视频里的真人替换成参考图里的角色，保持原片的动作、构图、机位和背景。

## 硬性前提（不可协商）

1. **所有推理只在 Windows 机上跑**：`labman00@192.168.10.75`，密钥 `/Users/mac/.workbuddy/keys/workbuddy_win`，ComfyUI `http://127.0.0.1:8188`。Mac 端只做编排、提交帧、轮询、传文件、ffmpeg 抽帧与封装，绝不跑任何模型推理或超分。
2. **ComfyUI 必须带 `--disable-comfy-compiler` 启动**，否则会随机报 `comfy_aimdo malloc_graph → stack overflow` 或被原生崩溃打死。启动/修复一律用 `scripts/win_clean_start.ps1`。
3. **成片等长**：`continuityKeepTail` 必须为 `false`，导出走 `pad_or_trim` 裁回源片帧数，不允许把衔接余量算进成片。
4. **四视图参考图整张使用**，不裁切、不删格、不改动任何一格（见 `references/prompt-playbook.md`）。

## 标准流程

1. **准备源片**：从 Win 的原始素材重采样到目标画布，24 fps，帧数取 H3 栅格（`17k+5`，如 413 / 379 / 362），且输出帧数不超过源片帧数。命令模板见 `references/win-environment.md`。
2. **参考图入库**：把角色四视图复制到 `E:\ComfyUI\input\`，统一改成 ASCII 文件名（中文名容易在参数里出问题）。参考图长边建议 ≤2556，`refImageSize` 用 `match`。
3. **写提示词**：按 `references/prompt-playbook.md` 的模板，控制在 **900–1400 字符**，每个人写出具体服装配色、领型、袖型、长度、鞋、发型，并明确「原服装一件都不能留」。超过 3k 字符会压掉换人效果。
4. **规划分段**：先用 `references/params-and-limits.md` 的实测表定分辨率与段长。当前硬约束：**1152×864 下单段有效生成帧数 ≤56**，超过就掉进换页区（72 帧 305 秒/步、107 帧 744 秒/步）。
5. **提交**：`scripts/build_h3_swap.py`，全部参数走环境变量（`WLP_W` / `WLP_H` / `WLP_FRAMES` / `WLP_SEGS` / `WLP_CONT` / `WLP_CONT_OVL` / `WLP_NOREFINE` / `WLP_TILING` / `WLP_EXPORT` / `WLP_SEED` / `WLP_PREFIX` / `WLP_SRC` / `WLP_PROMPT` / `WLP_START`）。脚本会在服务掉线时自动用 `win_clean_start.ps1` 拉起。
6. **监控**：`watch_job.py <prompt_id> <秒>`（在 Win 的 `E:\VideoShotSplitter\vogue768\`）；或读 `http://127.0.0.1:8188/internal/logs/raw` 拿实时进度。日志文件不一定是 `wlp4.err`——取决于哪个启动脚本拉起的实例，**以 API 的内存日志为准**。
7. **拼接与交付**：`scripts/concat_segments.py` 把分段拼成整片（`-c copy` 无损），ffprobe 核对帧数/分辨率/音轨，抽帧肉眼验收，再取回本地交付目录。

## 验证门槛（必须照着做）

**只读日志判断「成功」曾经放过一个三重影废片。** 每次出片必须抽帧看像素，至少 5 个帧位（0 / 25% / 50% / 75% / 末帧），外加每个段缝的缝前缝后两帧。检查项：

- 有没有人物横向重复、三重影、半透明叠影、马赛克
- 人物脸、发型、发饰、服装是否与设定图一致；两人有没有串脸
- 构图/景别是否仍与源片一致，有没有被推成特写或半身
- 结尾 2 秒是否仍保持原片景别

流程见 `references/verification-delivery.md`。

## 分辨率与段长速查

| 场景 | 分辨率 | 段长 | 有效帧 | 每步耗时 |
|---|---|---|---|---|
| 已验证可用 | 1152×864 | 51 + 5 融合 | 56 | 60–80 秒 |
| 已验证可用 | 1152×864 | 56（无融合） | 56 | 44–90 秒 |
| 已验证可用 | 1152×864 | 34 + 22 融合 | 56 | 44–90 秒 |
| 掉进换页区 | 1152×864 | 56 + 5 融合 | 61 | 172 秒 |
| 不可用 | 1152×864 | 72 | 72 | 305 秒 |
| 不可用 | 1152×864 | 107 | 107 | 744 秒 |

融合帧数只能取 `5 / 22 / 39 / 56`，中间值会被吸附（填 8 → 变 5）。详见 `references/params-and-limits.md`。

## 常见故障速查

| 症状 | 原因 | 处置 |
|---|---|---|
| 换人不生效，输出≈源片重绘 | 提示词过长（>3k 字符）压掉参考条件；或段列表为空导致参考图丢失 | 压缩提示词；检查 `segments[].refs` 是否真的随段提交 |
| 画面横向三重影 / 马赛克 | refine 开了空间 tiling 且 tile_count=3 | 关 tiling 走整帧二采，或按 `references/refine-export-concat.md` 调 tile |
| 整片拼接时报 `not enough memory ... cat_frames_variable_size` | `exportMode=all` 一次性拼 4.93 GB 内存 | 改 `exportMode=segments` + ffmpeg 拼接 |
| 段间动作明显断裂 | 融合帧数太低或没开 | 融合 22 帧（成本允许时），或缩短段长换融合预算 |
| 服务突然消失、日志无 traceback | 未带 `--disable-comfy-compiler`，或显存/内存被撑爆 | `win_clean_start.ps1` 重启后再跑，并把段长降一档 |

## 参考文件

- `references/win-environment.md` —— 主机、路径、启动参数、源片处理命令
- `references/params-and-limits.md` —— 实测帧数与耗时矩阵、融合帧数规则、段长规划算法
- `references/prompt-playbook.md` —— 四视图用法、有效提示词模板、长度阈值
- `references/refine-export-concat.md` —— 二采分块坑、分段导出、ffmpeg 拼接
- `references/verification-delivery.md` —— 抽帧验收清单、交付路径与局域网页面

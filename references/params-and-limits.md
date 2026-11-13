# 参数与实测上限

所有数字来自同一台机器（RTX 4060 Laptop 8 GB / 15.2 GB RAM）的真实运行记录，不是估算。

## 一、单段有效生成帧数的硬上限

在 **1152×864** 下，段长（body）加上融合帧数（lock）构成「有效生成帧数」，它决定每步耗时：

| 有效帧 | 配置示例 | 每步耗时 | 判定 |
|---|---|---|---|
| 22 | 22 帧首段（无融合） | 40.7 秒 | 可用 |
| 53 | 48 + 5 | 45–70 秒（推算） | 可用 |
| **56** | 56 无融合 / 51+5 / 34+22 | **44–90 秒** | **黄金档** |
| 61 | 56 + 5 | **172 秒** | 掉进换页区 |
| 72 | 72 无融合 | **305 秒** | 不可用 |
| 78 | 56 + 22 | 首步 >17 分钟 | 不可用 |
| 107 | 107 无融合 | **744 秒** | 不可用 |

结论：**56 就是这台卡的拐点**。多 5 帧（61）就贵 2–3 倍，不是线性关系，是显存被打满后开始反复换页。

推论：想改善段间连续性，**不能靠加融合帧数**，只能靠「缩短段长换融合预算」——例如 34 体 + 22 融合 = 56。

## 二、融合帧数（continuityOverlapFrames）

源码 `director/h3_motion_context.py`：

```python
CONTEXT_FRAME_CHOICES = (5, 22, 39, 56)
DEFAULT_CONTEXT_FRAMES = 22
```

- UI 填任意值都会 `snap` 到最近档（并列时取大）：填 8 → **5**；填 14 → 22；填 30 → 39
- 每段实际生成帧数 = `lock + settling(12) + body + lookahead(8)`，再对齐到 H3 栅格；实测日志里体现为 `context_end = lock + body`
- 融合质量取决于 lock（前文帧数），但**参考帧上限是 2 帧**（`MAX_CONTINUITY_REF_FRAMES = 2`），所以 5 帧融合的前文只有 0.2 秒，实际收益很弱；22 帧给到 0.92 秒才有意义
- 首段永远不 pin（`segment_index == 0` 直接返回 False）

## 三、段长规划算法

1. 总帧数 T 由源片与 `17k+5` 决定（例：T=413）
2. 选定有效帧预算 B（1152×864 下 B≤56）与融合 lock（0/5/22）
3. 段长 body = B − lock
4. 段数 n = ceil(T / body)，最后一段允许短（会内部对齐）

实例：
- B=56, lock=5 → body=51 → 413 = 51×7 + 56 = **8 段**
- B=56, lock=22 → body=34 → 413 = 34×12 + 5 ≈ **12 段**
- B=56, lock=0 → body=56 → 413 = 56×7 + 21 = **8 段**

## 四、显存与内存的相互关系

- 8 GB 显存 + 15.2 GB 内存：H3 权重约 26 GB，靠显存与内存之间来回搬；一旦激活值把显存顶到 7.8 GB 以上，就开始换页
- 判据：`nvidia-smi` 显存常驻 7.8–7.9 GB 且 `s/it` 超过 120 秒 → 已经进入换页区，应立刻降段长
- **主机内存也是硬门槛**：`exportMode=all` 在 1152×864 × 413 帧时需要一次性分配 4.93 GB 连续内存（float32 帧拼接），内存不足会抛 `RuntimeError: not enough memory ... cat_frames_variable_size`

## 五、采样设置

| 项 | 值 | 说明 |
|---|---|---|
| steps | 4 | 配 lightx2v turbo LoRA，再高收益有限、耗时线性增长 |
| cfg | 1.0 | turbo LoRA 训练值 |
| sampler | res_multistep | 模板默认 |
| scheduler | simple | |
| shift | 12（video）/ 3（audio） | |
| LoRA | `minimax_h3_ref2v_lightx2v_turbo_4step_v0.1_..._rank_20_bf16` | 4 步加速 |
| seed | 9783 | 复用同一 seed 便于跨画幅对比结构；512×896 老配置也是这个种子 |

## 六、二采（refine）

| 配置 | 结果 |
|---|---|
| `mode=refine` + tiling 关 | **可用**，51 帧实测二采 4 步 57.5 秒/步，单段多约 4 分钟，画面最干净 |
| `mode=refine` + tile_count=3 / overlap=64 | **出三重影**，整片报废（潜变量宽度取整算不齐） |
| `mode=refine` + tile_count=2 / overlap=128 | 报 `tensor a (7) vs b (6) at dim 4` 后回退一采（干净但等于没二采） |
| `mode=latent_upscale`（假关闭） | 报 `enlarge-only (got 1152×864 → 960×704)` 并留下叠影，**不要用** |
| 硬断开（删 `prompt["37"]["inputs"]["refine"]`、移除节点 44/45） | 完全不跑二采，干净 |

## 七、导出

- `exportMode=segments`：逐段写 `seg_XXXX.mp4`（+ `_pre` 一采版），写完后释放像素，**不占整片内存**，长片必须用这个
- `exportMode=all`：413 帧 / 1152×864 会因 4.93 GB 拼接内存失败
- 分段目录：`E:\ComfyUI\output\minimax_seg_export\<时间戳>\`

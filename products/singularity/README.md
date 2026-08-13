# Singularity — Kerr 黑洞屏保

实时桌面黑洞引力透镜。基于 Kerr 度规（旋转黑洞）的 GPU 测地线追踪。

## 环境要求

- **Windows 10 2004+**（`WDA_EXCLUDEFROMCAPTURE` 需要 2004 以上）
- **Rust 1.75+**：<https://rustup.rs>
- **GPU**：Direct3D 11.0+（带 `cs_5_0` compute shader 支持）
- **Windows SDK**（Visual Studio Build Tools 自带，或单独安装）

## 快速开始

```powershell
cd singularity
cargo run --release
```

全屏无边窗口，按 `Esc` 退出。

## 操控

| 按键 | 参数 | 效果 |
|------|------|------|
| `1` / `2` | a_spin ±0.05 | 黑洞自旋（0 = Schwarzschild, 0.998 = 极端 Kerr） |
| `3` / `4` | disk_inner ±0.3 | 吸积盘内半径（ISCO 边缘，默认 2.0） |
| `5` / `6` | disk_outer ±1.0 | 吸积盘外半径（散射盘，默认 12.0） |
| `←` / `→` | disk_roll ±0.05 | 视线旋转角（绕视线旋转整个画面） |
| `↑` / `↓` | lens_strength ±0.1 | 透镜影响半径（0.5-3.0，越大范围越广） |
| `9` / `0` | tint preset | 循环色调预设（中性/暖金/冷蓝/紫/玫瑰） |
| `r` | 全部 | 重置默认值 |
| `Tab` | — | 最小化 / 恢复（临时切回桌面） |
| `Esc` | — | 退出 |

## 渲染管线

```
GDI / Desktop Duplication → ID3D11Texture2D (SRV)
                                  ↓
                         Compute Shader (cs_5_0)
                      Kerr 测地线追踪, 每像素独立
                                  ↓
                         ID3D11Texture2D (UAV)
                                  ↓
                         CopyResource → SwapChain → Present
```

三层 Rust 模块：

| 模块 | 职责 |
|------|------|
| `capture.rs` | 桌面捕获。优先 Desktop Duplication API，回退 GDI `BitBlt` |
| `blackhole.rs` | Compute shader 管理。运行时 `D3DCompile` 编译 HLSL，`CSSetShader` + `Dispatch` 执行 |
| `render.rs` | SwapChain 呈现。DXGI flip model，无边全屏窗口 |

## 物理模型

### Kerr 度规 (Boyer-Lindquist 坐标)

旋转黑洞由两个参数决定：质量 M（设为 1）和自旋 a（默认 0.9）。度规：

```
ds² = -(1-2Mr/Σ)dt² - (4aMrsin²θ/Σ)dtdφ + (Σ/Δ)dr² + Σdθ²
    + (r²+a²+2Ma²rsin²θ/Σ)sin²θdφ²

其中 Σ = r² + a²cos²θ,  Δ = r² - 2Mr + a²
```

### 类光测地线积分

每条光线（屏幕像素）对应一组 Carter 常数 (λ, q²)，决定其轨道：

```
λ = -α·sin(θ_obs)        （方位角冲击参数）
q² = β² + (α²-a²)cos²θ_obs  （Carter 常数）
```

在 Mino 时间 μ 下用 **RK4 自适应步长** 积分 3 个自由度 (r, θ, φ)，最多 600 步。步长受限于距极轴距离，防止 BL 坐标在 θ=0,π 处的奇点发散。

### 双区域策略

| 区域 | 条件 | 方法 | 像素占比 |
|------|------|------|----------|
| 近场 | b < r_out + 3.0 | RK4 数值积分（600 步） | ~15% |
| 远场 | b ≥ r_out + 3.0 | 解析 1/b 弱偏折公式 | ~85% |

### 吸积盘

几何薄盘，赤道面 θ=π/2，Shakura-Sunyaev 温度剖面：

```
T(r) ∝ r^(-3/4) × (1-√(r_in/r))^(1/4)
```

- **Doppler 因子**：g = 1/(u^t × (1-λΩ))，包含引力红移 + 轨道运动的多普勒频移
- **相对论束流**：观测强度 ∝ g^beam（beam = 2.8）
- **光子环增强**：内边缘附加光滑发射 exp(-(r-r_in)×2.0)
- **噪声纹理**：双层 wrap-noise 模拟螺旋湍流结构

### 引力透镜 & 色差

- **远场**：解析偏折，RGB 三通道分离采样，蓝光偏折约 3.5% 更多
- **近场逃逸光线**：同样三通道分离采样，偏折差约 2.5%
- **星空**：基于 hash 的稀疏星场（8% 密度），采样自光线出射方向 → 自然呈现被透镜弯曲的弧形星轨

## 参考

- [ghostty-blackhole](https://github.com/ghostty-org/ghostty-blackhole) — Schwarzschild 黑洞 shader，远场解析 + 天空平面反向投影 + 色差
- [Eric Bruneton, "Real-Time High-Quality Rendering of Non-Rotating Black Holes"](https://arxiv.org/abs/2010.08735) — 预计算偏折纹理 + 自适应反走样
- 本项目选择 Kerr 而非 Schwarzschild：D 形阴影 + 参考系拖拽 + 非对称 Doppler，视觉效果更丰富，代价是 BL 坐标有极轴奇点。

## 项目结构

```
singularity/
├── Cargo.toml
├── README.md
└── src/
    ├── main.rs          # 事件循环, 键盘输入, 管线串联
    ├── blackhole.hlsl   # Kerr 测地线 CS (~400 行 HLSL)
    ├── blackhole.rs     # D3DCompile + Dispatch 管理
    ├── capture.rs       # 桌面捕获 (Desktop Duplication / GDI)
    └── render.rs        # SwapChain 呈现
```

## 故障排除

| 症状 | 原因 | 解决 |
|------|------|------|
| 启动报 `0x80070057` | constant buffer 大小不匹配 / 显卡不支持 | 更新 GPU 驱动 |
| 帧率低 | MAX_STEPS=600 对老旧 GPU 压力大 | 改为 400-500（`blackhole.hlsl:2`），远场不受影响 |
| 画面无限递归 | `SetWindowDisplayAffinity` 失败 | 系统版本低于 Win10 2004，升级系统 |
| 编译失败 | 缺 Windows SDK / Rust 版本过旧 | `rustup update`；安装 VS Build Tools |
| 黑色屏幕 | Desktop Duplication 初始化失败 + GDI 回退也失败 | 更新显卡驱动；检查是否有其他全屏程序占用 |

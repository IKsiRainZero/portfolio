# Singularity 技术栈

## 语言与运行时
- **Rust** (stable, edition 2024)
- 无 GC、无运行时依赖、零成本抽象、直接调用 Win32 COM API

## 图形与 GPU
- **DirectX 11** — Desktop Duplication API 需要 D3D11
- **HLSL Compute Shader** (cs_5_0) — 引力透镜光线追踪在 GPU 上每像素并行
- **DirectX 11 Pixel Shader** — 全屏四边形采样 + HDR tone mapping
- **SwapChain** — vsync present 到显示器

## 桌面捕获
- **windows-rs** crate → `IDXGIOutputDuplication`
  - `AcquireNextFrame()` 零拷贝获取桌面纹理
  - `ReleaseFrame()` 释放后桌面才能更新下一帧
  - 支持多显示器枚举

## 窗口与输入
- **winit** — 全屏窗口创建 + 事件循环
- 键盘/鼠标事件 → 任意输入退出
- 可选：系统托盘图标 (tray-icon crate) 用于手动触发

## 数学
- **glam** — 向量/矩阵运算（比 nalgebra 轻量，适合 GPU 场景）
- **noise** — Perlin noise 生成黑洞游荡路径

## 打包分发
- `cargo build --release` → 单个 .exe
- 无外部 DLL 依赖（静态链接 windows-rs）
- 目标文件大小 < 5MB（不含调试符号）

## 不引入
- 不使用任何游戏引擎（Bevy/Fyrox 过度）
- 不使用 WGPU（Desktop Duplication 需要原生 DX11，WGPU 抽象层阻隔）
- 不使用 CUDA/OpenCL（通用计算 API，对图形管线集成不如 compute shader 直接）

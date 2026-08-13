# Singularity 架构

## 整体架构
```
singularity.exe
├── desktop_capture     ← Desktop Duplication API (IDXGIOutputDuplication)
│   ├── init             ← 枚举显示器，创建 d3d11 device + duplication interface
│   └── loop             ← AcquireNextFrame() → GPU texture (零拷贝)
│
├── black_hole           ← 黑洞物理模拟
│   ├── position         ← 游荡策略（随机漫步 / Perlin noise path）
│   ├── mass             ← 质量变化（越大吸入越多，视野扭曲半径越大）
│   └── accretion        ← 吸积盘粒子系统（被吸入的内容碎片环绕发光）
│
├── lens_shader          ← Compute Shader (HLSL)
│   ├── schwarzschild    ← Schwarzschild 度规光线追踪 — 引力透镜
│   ├── doppler          ← 相对论多普勒频移 — 蓝移（接近）+ 红移（远离）
│   └── brightness       ← 光强放大 — 靠近事件视界的像素更亮
│
├── render               ← 全屏四边形渲染
│   ├── fullscreen_quad  ← 两个三角形覆盖全屏
│   ├── pixel_shader     ← 采样 compute shader 输出 + HDR tone mapping
│   └── vsync            ← present 到显示器
│
└── input                ← winit 事件循环
    ├── idle_detect      ← 可选手动触发按钮 / 托盘图标
    ├── keyboard         ← 任意键退出
    └── mouse            ← 鼠标移动退出
```

## 数据流
```
Desktop Duplication → GPU Texture A (桌面)
                    → Compute Shader (Schwarzschild raytrace + Doppler + lens)
                    → GPU Texture B (扭曲结果)
                    → Pixel Shader (fullscreen quad, tone map)
                    → SwapChain Present (显示器)

吸积盘粒子：
  被吸入的桌面碎片 → 粒子缓冲区 → Geometry Shader 展开光带 → Blend additively
```

## 事件视界半径
黑洞周围内容被吸到黑洞中心附近，剩余空间填充黑色（事件视界）。外部内容保留原位置但被透镜拉伸/压缩。

## 游荡策略
基于 Perlin noise 生成平滑随机路径，速度可调。黑洞从不离开屏幕（边界反弹 + 边缘引力减小）。

## 共享(演示)模式
- 单 .exe，无安装、无运行时依赖
- 手动双击启动，任意键/鼠标移动退出
- 不写注册表、不安装到 System32、不开机自启

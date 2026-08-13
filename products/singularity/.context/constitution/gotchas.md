# Gotchas

windows-rs 0.58 + winit 0.29 开发中的 API 陷阱速查。

## windows-rs 0.58 Feature Gating

很多方法和类型**静默不可用**，直到添加对应的 Cargo feature：

| Feature | 解锁内容 |
|---|---|
| `Win32_Graphics_Direct3D` | `D3D_FEATURE_LEVEL`, `D3D_DRIVER_TYPE` 常量 |
| `Win32_Graphics_Dxgi_Common` | `DXGI_MODE_DESC`, `DXGI_SAMPLE_DESC`, `DXGI_FORMAT_*`, `CreateTexture2D`, `GetDesc` on `IDXGIOutputDuplication` |

当前 Cargo.toml 所需 feature 集合：
```toml
windows = { features = [
    "Win32_Graphics_Direct3D11",
    "Win32_Graphics_Direct3D",
    "Win32_Graphics_Dxgi",
    "Win32_Graphics_Dxgi_Common",
    "Win32_Foundation",
    "Win32_System_Com",
] }
```

## D3D11CreateDevice 参数

```rust
// adapter: IDXGIAdapter1 不能直接传入，需 cast 到 IDXGIAdapter
let adapter1: IDXGIAdapter1 = factory.EnumAdapters1(0)?;
let adapter: IDXGIAdapter = adapter1.cast()?;

// software: NULL HMODULE 的正确写法
None::<&HMODULE>   // ✓  不可 None::<HMODULE> 或 None::<HINSTANCE>

// sdkversion: 直接用 7（D3D11_SDK_VERSION 常量值），不用引常量名
7
```

## D3D11_TEXTURE2D_DESC 字段类型

```rust
D3D11_TEXTURE2D_DESC {
    BindFlags: 8u32,            // D3D11_BIND_SHADER_RESOURCE.0 as u32
    CPUAccessFlags: 0u32,       // 不是 D3D11_CPU_ACCESS_FLAG(0)
    MiscFlags: 0u32,            // 不是 D3D11_RESOURCE_MISC_FLAG(0)
    Usage: D3D11_USAGE_DEFAULT, // 这是 newtype，OK 直接赋值
    Format: DXGI_FORMAT_B8G8R8A8_UNORM, // newtype，OK
    // ...其他字段正常
}
```

**规则**：`_FLAG` 结尾的类型（`D3D11_BIND_FLAG`, `D3D11_CPU_ACCESS_FLAG` 等）是 newtype，但对应 struct 字段是 `u32`，需 `.0 as u32`。

## DXGI 类型

- `DXGI_PRESENT` — newtype，`DXGI_PRESENT(0)` 表示无特殊 flag
- `IDXGISwapChain::Present` — 返回 `HRESULT`，需 `.ok()?`
- `IDXGIFactory::CreateSwapChain` — 返回 `HRESULT`，需 `.ok()?`
- `IDXGIOutputDuplication::GetDesc` — 直接返回值，**不用 `?`**
- `DXGI_SWAP_CHAIN_DESC.OutputWindow` — 类型 `HWND`，用 `HWND(raw_ptr)` 构造
- `DXGI_SWAP_CHAIN_DESC.Windowed` — 类型 `BOOL`，用 `BOOL(1)` 或 `true.into()`
- `GetBuffer::<T>(index)` — 泛型方法直接返回 `Result<T>`，不用 `&mut Option<T>`

## D3DCompile & Shader

- `D3DCompile` — `ppcode` 参数是 `*mut Option<ID3DBlob>` 直接传入，**不能**包 `Some()`
- `pperrormsgs` 参数是 `Option<*mut Option<ID3DBlob>>`，需 `Some(&mut errors as *mut _)`
- `D3DCompile` 入口/目标字符串用 `CString::new().unwrap()` 转 `PCSTR`
- **"Internal error: unread predicate"** — D3DCompile 优化器在复杂控制流（RK4 循环）上崩溃。必须用 `D3DCOMPILE_SKIP_OPTIMIZATION`。`float` 版 shader 也一样 crash，不是 `double` 的问题。
- `CreateComputeShader` — `None::<&ID3D11ClassLinkage>`，不是 `None::<ID3D11ClassLinkage>`
- Shader Model 5.0 没有 double 精度内建函数（sin/cos/sqrt/pow 无 double 重载），会静默截断为 float→double
- HLSL cbuffer 和 Rust struct 必须 16-byte 对齐

## Compute Shader Dispatch

- `CSSetShaderResources` — 传 `Option<&[Option<ID3D11ShaderResourceView>]>`
- `CSSetUnorderedAccessViews` — **签名不同**，传 `*const Option<ID3D11UnorderedAccessView>` + count
- `CSSetConstantBuffers` — 传 `Option<&[Option<ID3D11Buffer>]>`
- Dispatch 后必须 **unbind** SRV/UAV/CB，否则后续 `CopyResource` 触发 D3D debug 层警告

## GDI Capture

- `GetDC(None)` — `None` 表示整个屏幕（`HWND` 为 NULL）
- 全屏窗口创建后 GDI 抓的是窗口自身（黑），不是桌面。必须在 `window.build()` **之前**抓。
- `BitBlt` 返回 `Result<(), Error>`（windows-rs 0.58），不是 `BOOL`
- `HDC.0.is_null()` / `HBITMAP.0.is_null()` — 用 `.is_null()` 而非 `== 0`
- `GetDeviceCaps(screen_dc, HORZRES/VERTRES)` 获取屏幕尺寸
- GDI 清理用 `let _ =` 抑制 `#[must_use]` 警告
- GDI 路径不适用每帧抓取（全屏窗口盖住桌面后无法穿透），DD 路径保持每帧抓取

## Mino 时间 Kerr 积分

- 大 r 处 `v_r ≈ r²`（约 250000 at r=500），步长必须与 `r²` 成反比
- 用 `h = 0.03 * r / v_approx` 使每步 Δr ≈ 3% r，避免数值爆炸
- 600 步从 r=500 积分到视界，往返约 360 步
- `radial_R` 预检可过滤阴影内光线（`R < 0` → 直接黑色）

## winit 0.29 窗口启动

- 全屏 borderless 窗口创建时经历多次 resize（800×600→822×656→2560×1440）
- 启动事件洪可能阻塞 `RedrawRequested`，需在进入事件循环前主动 `window.request_redraw()`
- 任意键退出会被系统按键（Alt 修饰符残留等）误触发，改为特定键（Escape）
- winit 0.29 的 `Key::Named(NamedKey::Escape)` 匹配，`logical_key` 是 `Key` 枚举不是 `Option`

## winit 0.29 事件循环

```rust
// EventLoop::new() 返回 Result，需要 ? 或 unwrap
let event_loop = EventLoop::new()?;

// 闭包签名：FnMut(Event, &EventLoopWindowTarget)
event_loop.run(move |event, elwt| {
    elwt.set_control_flow(ControlFlow::Poll);
    // ControlFlow 无 Exit 变体，退出的方式：
    elwt.exit();
})?;

// RedrawRequested 是 WindowEvent 的子变体，不是 Event 的直接变体
match event {
    Event::WindowEvent { event: WindowEvent::RedrawRequested, .. } => { /* render */ }
    Event::AboutToWait => { window.request_redraw(); }
    _ => {}
}

// KeyboardInput 字段名是 event，不是 input
WindowEvent::KeyboardInput { event: key_event, .. } => { ... }
// key_event.state == ElementState::Pressed 判断按下
```

## raw-window-handle 0.6

winit 0.29 使用 rwh 0.6（非 0.5），Cargo.toml 中需要声明：
```toml
raw-window-handle = "0.6"
```

获取 HWND：
```rust
use raw_window_handle::{HasWindowHandle, RawWindowHandle};
let hwnd = match window.window_handle()?.as_raw() {
    RawWindowHandle::Win32(h) => h.hwnd.get() as *mut std::ffi::c_void,
    _ => panic!(),
};
```

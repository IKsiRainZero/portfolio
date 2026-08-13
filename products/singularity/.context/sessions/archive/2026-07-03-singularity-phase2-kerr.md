# Phase 2: Kerr Black Hole Compute Shader — Session Archive

Date: 2026-07-03
Status: in progress — visible black hole + lensing, disk needs work

## What was built

Kerr rotating black hole shader pipeline:
- `capture.rs` → GDI fallback (Desktop Duplication unsupported on user's Intel iGPU)
- `blackhole.hlsl` → Kerr geodesic RK4 integration in Mino time
- `blackhole.rs` → D3D11 compute shader host: D3DCompile + dispatch
- `main.rs` → pipeline wiring: capture → blackhole.process() → render

## What works

- GDI desktop capture at init (before window creation, avoids feedback loop)
- D3DCompile with SKIP_OPTIMIZATION (optimizer crashes on complex shader)
- Kerr geodesic integration with adaptive step h ∝ 1/r²
- Gravitational lensing (radial displacement based on distance from shadow)
- Black hole shadow (radial_R pre-check + horizon capture)
- Accretion disk with Tanner Helland blackbody color
- Doppler asymmetry (60% mix)
- Size grow animation (fov_scale 110→75 over 25s)
- Lissajous drift movement
- Escape to exit (specific key, not any key)

## Key gotchas discovered

1. **Mino time RK4 numerical instability**: At large r, v_r ≈ r² ≈ 250000, so even tiny step sizes produce enormous r changes. Fix: h ∝ 1/r² via `h = 0.03*r/r² = 0.03/r`.

2. **D3DCompile "Internal error: unread predicate"**: Optimization passes crash on complex control flow in float shader. Must use D3DCOMPILE_SKIP_OPTIMIZATION. (Was originally double; float rewrite didn't help.)

3. **GDI feedback loop**: Fullscreen window covers desktop. GDI `GetDC(NULL)` captures the window (black), not desktop. Fix: capture at init before `window.build()`, then no-op per frame for GDI.

4. **Window creation order matters**: `WindowBuilder::build()` may show window immediately. Must capture desktop BEFORE creating window.

5. **winit fullscreen resize events**: Window goes through multiple resize events (800x600 → 822x656 → 2560x1440) during creation. RedrawRequested may not fire before first user input. Fix: call `window.request_redraw()` before event loop.

6. **Exit sensitivity**: Any-key-exit causes premature exit from system key events (Alt modifier). Changed to Escape-only.

7. **D3D11 device context cloning**: Multiple `ID3D11DeviceContext::clone()` calls share same immediate context. Safe as long as single-threaded, but D3D debug layer may warn.

## Reference projects analyzed

- **Bruneton (black_hole_shader)**: Schwarzschild, precomputed lookup textures for O(1) ray deflection + disc intersection. The academic gold standard.
- **XboxNahida (ghostty-blackhole-main)**: Bruneton's physics ported to numerical integration (48-step leapfrog). Directly applicable as reference. Same language (GLSL→HLSL).

### XboxNahida key params (baseline for comparison)

| Param | Value | Notes |
|---|---|---|
| HOLE_RADIUS | 0.02 | fraction of screen height |
| DISK_INNER | 1.8 r_s | just outside photon sphere (1.5 r_s) |
| DISK_OUTER | 8.0 r_s | |
| DISK_TEMP | 5500 K | peak temperature, normalized |
| DISK_GAIN | 2.2 | |
| DISK_OPACITY | 0.9 | |
| DOPPLER_MIX | 0.6 | blend g with 1.0 |
| DISK_BEAM | 2.5 | beaming exponent |
| N_STEPS | 48 | very few steps |
| B_CRIT | 2.598 | photon sphere impact param |

### Gaps to fill (next session)

1. **Disk streaks/noise**: procedural noise on disk surface (vnoiseWrapY) — primary source of "realism"
2. **Multiple disk crossings**: accumulate emission across all crossings with transmittance decay
3. **Far-field weak deflection**: most pixels don't need geodesic integration
4. **Background back-projection**: project exit ray to sky plane for correct lensing
5. **Step size simplification**: leapfrog + `dt=clamp(0.16*r, 0.03, 1.5)` is simpler and more robust than Mino time RK4

## Current file state

- `src/capture.rs` — dual backend (Duplication + GDI), GDI captures at init only
- `src/blackhole.rs` — D3DCompile SKIP_OPTIMIZATION, process(time), animated params
- `src/blackhole.hlsl` — Kerr RK4 600 steps, Tanner Helland blackbody, smoothstep banding, 60% Doppler mix, radial lensing
- `src/main.rs` — capture→shader→render pipeline, Escape exit, Instant time tracking
- `src/render.rs` — unchanged from Phase 1
- `.context/` — reference projects downloaded (black_hole_shader-master, ghostty-blackhole-main-main)

## Reference project locations

- `.context/black_hole_shader-master/` — Bruneton WebGL2 reference
- `.context/ghostty-blackhole-main-main/` — XboxNahida Windows D3D11 reference

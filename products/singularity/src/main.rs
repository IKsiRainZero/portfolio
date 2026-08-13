mod blackhole;
mod capture;
mod render;

use std::cell::RefCell;
use std::time::Instant;

use raw_window_handle::{HasWindowHandle, RawWindowHandle};
use winit::event::{ElementState, Event, MouseButton, MouseScrollDelta, WindowEvent};
use winit::event_loop::{ControlFlow, EventLoop};
use winit::window::{Fullscreen, WindowBuilder};

use blackhole::BlackholeEffect;
use capture::DesktopCapture;
use render::Renderer;

extern "system" {
    fn SetWindowDisplayAffinity(hwnd: *mut std::ffi::c_void, affinity: u32) -> i32;
    fn ShowWindow(hwnd: *mut std::ffi::c_void, nCmdShow: i32) -> i32;
}
const WDA_EXCLUDEFROMCAPTURE: u32 = 0x11;
const SW_MINIMIZE: i32 = 6;
const SW_RESTORE: i32 = 9;

fn main() -> anyhow::Result<()> {
    let event_loop = EventLoop::new()?;

    // capture desktop BEFORE creating fullscreen window
    let capture = RefCell::new(DesktopCapture::init()?);
    {
        let mut cap = capture.borrow_mut();
        cap.acquire_frame()?;
    }

    let window = WindowBuilder::new()
        .with_fullscreen(Some(Fullscreen::Borderless(None)))
        .with_title("Singularity")
        .build(&event_loop)?;

    let hwnd = match window.window_handle()?.as_raw() {
        RawWindowHandle::Win32(h) => h.hwnd.get() as *mut std::ffi::c_void,
        _ => anyhow::bail!("not on Windows"),
    };

    // Exclude our window from screen capture so GDI sees the desktop behind us
    unsafe {
        let ret = SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE);
        if ret == 0 {
            eprintln!("SetWindowDisplayAffinity failed — GDI capture may show feedback loop");
        }
    }

    let blackhole = RefCell::new({
        let cap = capture.borrow();
        BlackholeEffect::new(
            &cap.device,
            cap.context.clone(),
            &cap.cached,
            cap.size().0,
            cap.size().1,
        )?
    });

    let renderer = RefCell::new({
        let cap = capture.borrow();
        Renderer::new(
            hwnd,
            &cap.device,
            cap.context.clone(),
            cap.size().0,
            cap.size().1,
        )?
    });

    eprintln!("Singularity — Mouse:drag=rotate/tilt, scroll=lens | Keys:1-6=params, Q/E=view angle, G=gravity mode, arrows=roll/lens, 9/0=tint, r=reset, Tab=minimize, Esc=exit");

    window.request_redraw();

    let start = Instant::now();
    let minimized: RefCell<bool> = RefCell::new(false);
    let mouse_dragging: RefCell<bool> = RefCell::new(false);
    let mouse_last_x: RefCell<f64> = RefCell::new(0.0);
    let mouse_last_y: RefCell<f64> = RefCell::new(0.0);

    event_loop.run(move |event, elwt| {
        elwt.set_control_flow(ControlFlow::Poll);

        match event {
            Event::WindowEvent { event, .. } => match event {
                WindowEvent::CloseRequested => elwt.exit(),
                WindowEvent::KeyboardInput { event: key_event, .. } => {
                    if key_event.state == ElementState::Pressed {
                        use winit::keyboard::{Key, NamedKey};
                        match &key_event.logical_key {
                            Key::Named(NamedKey::Escape) => elwt.exit(),
                            // ── adjustable parameters ──
                            Key::Character(c) => {
                                let mut bh = blackhole.borrow_mut();
                                match c.as_str() {
                                    "1" => { bh.a_spin = (bh.a_spin - 0.05).max(0.0); eprintln!("a_spin = {:.2}", bh.a_spin); }
                                    "2" => { bh.a_spin = (bh.a_spin + 0.05).min(0.998); eprintln!("a_spin = {:.2}", bh.a_spin); }
                                    "3" => { bh.disk_inner = (bh.disk_inner - 0.3).max(1.5); eprintln!("disk_inner = {:.1}", bh.disk_inner); }
                                    "4" => { bh.disk_inner = (bh.disk_inner + 0.3).min(bh.disk_outer - 1.0); eprintln!("disk_inner = {:.1}", bh.disk_inner); }
                                    "5" => { bh.disk_outer = (bh.disk_outer - 1.0).max(bh.disk_inner + 1.0); eprintln!("disk_outer = {:.1}", bh.disk_outer); }
                                    "6" => { bh.disk_outer = (bh.disk_outer + 1.0).min(25.0); eprintln!("disk_outer = {:.1}", bh.disk_outer); }
                                    "9" => {
                                        let presets = [
                                            [1.0, 1.0, 1.0],
                                            [1.0, 0.82, 0.55],
                                            [0.70, 0.82, 1.0],
                                            [0.85, 0.75, 1.0],
                                            [1.0, 0.65, 0.70],
                                        ];
                                        let cur = bh.disk_tint;
                                        let idx = presets.iter().position(|p| (p[0] - cur[0]).abs() < 0.01 && (p[1] - cur[1]).abs() < 0.01 && (p[2] - cur[2]).abs() < 0.01).unwrap_or(0);
                                        let next = (idx + 1) % presets.len();
                                        bh.disk_tint = presets[next];
                                        eprintln!("tint = {:?}", bh.disk_tint);
                                    }
                                    "0" => {
                                        let presets = [
                                            [1.0, 1.0, 1.0],
                                            [1.0, 0.82, 0.55],
                                            [0.70, 0.82, 1.0],
                                            [0.85, 0.75, 1.0],
                                            [1.0, 0.65, 0.70],
                                        ];
                                        let cur = bh.disk_tint;
                                        let idx = presets.iter().position(|p| (p[0] - cur[0]).abs() < 0.01 && (p[1] - cur[1]).abs() < 0.01 && (p[2] - cur[2]).abs() < 0.01).unwrap_or(0);
                                        let prev = if idx == 0 { presets.len() - 1 } else { idx - 1 };
                                        bh.disk_tint = presets[prev];
                                        eprintln!("tint = {:?}", bh.disk_tint);
                                    }
                                    "g" => { bh.gravity_mode = !bh.gravity_mode; eprintln!("gravity_mode = {}", bh.gravity_mode); }
                                    "q" => { bh.theta_obs_offset = (bh.theta_obs_offset - 0.05).max(-0.8); eprintln!("theta_obs = {:.2} (offset {:.2})", 1.20 + bh.theta_obs_offset, bh.theta_obs_offset); }
                                    "e" => { bh.theta_obs_offset = (bh.theta_obs_offset + 0.05).min(1.2); eprintln!("theta_obs = {:.2} (offset {:.2})", 1.20 + bh.theta_obs_offset, bh.theta_obs_offset); }
                                    "r" => {
                                        bh.a_spin = 0.9;
                                        bh.disk_inner = 2.3;
                                        bh.disk_outer = 12.0;
                                        bh.theta_obs_offset = 0.0;
                                        bh.disk_roll = 0.35;
                                        bh.disk_tint = [1.0, 1.0, 1.0];
                                        bh.lens_strength = 1.0;
                                        bh.gravity_mode = false;
                                        bh.gravity_time = 0.0;
                                        eprintln!("reset to defaults");
                                    }
                                    _ => {}
                                }
                            }
                            Key::Named(NamedKey::ArrowLeft)  => { blackhole.borrow_mut().disk_roll -= 0.05; eprintln!("disk_roll = {:.2}", blackhole.borrow().disk_roll); }
                            Key::Named(NamedKey::ArrowRight) => { blackhole.borrow_mut().disk_roll += 0.05; eprintln!("disk_roll = {:.2}", blackhole.borrow().disk_roll); }
                            Key::Named(NamedKey::ArrowUp)    => { let v = blackhole.borrow().lens_strength; blackhole.borrow_mut().lens_strength = (v + 0.1).min(3.0); eprintln!("lens_strength = {:.1}", v + 0.1); }
                            Key::Named(NamedKey::ArrowDown)  => { let v = blackhole.borrow().lens_strength; blackhole.borrow_mut().lens_strength = (v - 0.1).max(0.5); eprintln!("lens_strength = {:.1}", v - 0.1); }
                            Key::Named(NamedKey::Tab) => {
                                let mut m = minimized.borrow_mut();
                                *m = !*m;
                                if *m {
                                    unsafe { ShowWindow(hwnd, SW_MINIMIZE); }
                                } else {
                                    unsafe { ShowWindow(hwnd, SW_RESTORE); }
                                }
                            }
                            _ => {}
                        }
                    }
                }
                WindowEvent::CursorMoved { position, .. } => {
                    let mut last_x = mouse_last_x.borrow_mut();
                    let mut last_y = mouse_last_y.borrow_mut();
                    let dx = position.x - *last_x;
                    let dy = position.y - *last_y;
                    *last_x = position.x;
                    *last_y = position.y;
                    if *mouse_dragging.borrow() {
                        let mut bh = blackhole.borrow_mut();
                        bh.disk_roll += dx as f32 * 0.005;
                        bh.theta_obs_offset = (bh.theta_obs_offset + dy as f32 * 0.003).clamp(-0.8, 1.2);
                    }
                }
                WindowEvent::MouseInput { state, button, .. } => {
                    if button == MouseButton::Left {
                        *mouse_dragging.borrow_mut() = state == ElementState::Pressed;
                    }
                }
                WindowEvent::MouseWheel { delta, .. } => {
                    let dy = match delta {
                        MouseScrollDelta::LineDelta(_, y) => y,
                        MouseScrollDelta::PixelDelta(pos) => pos.y as f32 * 0.01,
                    };
                    let mut bh = blackhole.borrow_mut();
                    bh.lens_strength = (bh.lens_strength + dy * 0.1).clamp(0.5, 3.0);
                    eprintln!("lens_strength = {:.1}", bh.lens_strength);
                }
                WindowEvent::RedrawRequested => {
                    if *minimized.borrow() { return; }
                    let elapsed = start.elapsed().as_secs_f32();
                    match capture.borrow_mut().acquire_frame() {
                        Ok(_tex) => {
                            match blackhole.borrow_mut().process(elapsed) {
                                Ok(output) => {
                                    if let Err(e) = renderer.borrow().render(&output) {
                                        eprintln!("render error: {e}");
                                    }
                                }
                                Err(e) => eprintln!("shader error: {e}"),
                            }
                        }
                        Err(e) => eprintln!("capture error: {e}"),
                    }
                }
                _ => {}
            },
            Event::AboutToWait => {
                window.request_redraw();
            }
            _ => {}
        }
    })?;
    Ok(())
}

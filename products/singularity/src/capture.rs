use anyhow::{Context, Result};
use std::mem;
use windows::core::Interface;
use windows::Win32::Foundation::HMODULE;
use windows::Win32::Graphics::Direct3D::*;
use windows::Win32::Graphics::Direct3D11::*;
use windows::Win32::Graphics::Dxgi::*;
use windows::Win32::Graphics::Dxgi::Common::*;
use windows::Win32::Graphics::Gdi::*;

enum Backend {
    Duplication(IDXGIOutputDuplication),
    Gdi,
}

pub struct DesktopCapture {
    pub device: ID3D11Device,
    pub context: ID3D11DeviceContext,
    backend: Backend,
    pub cached: ID3D11Texture2D,
    width: u32,
    height: u32,
}

impl DesktopCapture {
    pub fn init() -> Result<Self> {
        // ── Fast path: Desktop Duplication ──
        if let Ok(cap) = Self::init_duplication() {
            return Ok(cap);
        }

        // ── Fallback: GDI capture ──
        Self::init_gdi().context("Desktop Duplication and GDI capture both failed")
    }

    fn init_duplication() -> Result<Self> {
        let factory: IDXGIFactory1 = unsafe { CreateDXGIFactory1() }?;

        for adapter_idx in 0..4 {
            let adapter1 = match unsafe { factory.EnumAdapters1(adapter_idx) } {
                Ok(a) => a,
                Err(_) => break,
            };
            let adapter: IDXGIAdapter = match adapter1.cast() {
                Ok(a) => a,
                Err(_) => continue,
            };

            for output_idx in 0..4 {
                let output = match unsafe { adapter.EnumOutputs(output_idx) } {
                    Ok(o) => o,
                    Err(_) => break,
                };
                let output1: IDXGIOutput1 = match output.cast() {
                    Ok(o) => o,
                    Err(_) => continue,
                };

                let mut device: Option<ID3D11Device> = None;
                let mut context: Option<ID3D11DeviceContext> = None;
                let mut level = D3D_FEATURE_LEVEL_11_0;

                if unsafe {
                    D3D11CreateDevice(
                        Some(&adapter),
                        D3D_DRIVER_TYPE_UNKNOWN,
                        None::<&HMODULE>,
                        D3D11_CREATE_DEVICE_BGRA_SUPPORT,
                        None,
                        7,
                        Some(&mut device as *mut _),
                        Some(&mut level as *mut _),
                        Some(&mut context as *mut _),
                    )
                }
                .is_err()
                {
                    continue;
                }

                let device = device.unwrap();
                let context = context.unwrap();

                let duplication = match unsafe { output1.DuplicateOutput(&device) } {
                    Ok(d) => d,
                    Err(_) => continue,
                };

                let desc = unsafe { duplication.GetDesc() };
                let width = desc.ModeDesc.Width;
                let height = desc.ModeDesc.Height;

                let tex_desc = D3D11_TEXTURE2D_DESC {
                    Width: width,
                    Height: height,
                    MipLevels: 1,
                    ArraySize: 1,
                    Format: desc.ModeDesc.Format,
                    SampleDesc: DXGI_SAMPLE_DESC {
                        Count: 1,
                        Quality: 0,
                    },
                    Usage: D3D11_USAGE_DEFAULT,
                    BindFlags: D3D11_BIND_SHADER_RESOURCE.0 as u32,
                    CPUAccessFlags: 0,
                    MiscFlags: 0,
                };
                let mut cached: Option<ID3D11Texture2D> = None;
                unsafe {
                    device
                        .CreateTexture2D(&tex_desc, None, Some(&mut cached as *mut _))?;
                }
                let cached = cached.unwrap();

                // drain initial frames
                unsafe {
                    for _ in 0..5 {
                        let mut info = DXGI_OUTDUPL_FRAME_INFO::default();
                        let mut res = None;
                        if duplication
                            .AcquireNextFrame(100, &mut info, &mut res)
                            .is_ok()
                        {
                            duplication.ReleaseFrame()?;
                        }
                    }
                }

                return Ok(Self {
                    device,
                    context,
                    backend: Backend::Duplication(duplication),
                    cached,
                    width,
                    height,
                });
            }
        }

        anyhow::bail!("no Desktop Duplication adapter found")
    }

    fn init_gdi() -> Result<Self> {
        let (width, height) = unsafe {
            let screen_dc = GetDC(None);
            if screen_dc.0.is_null() {
                anyhow::bail!("GetDC failed");
            }
            let w = GetDeviceCaps(screen_dc, HORZRES) as u32;
            let h = GetDeviceCaps(screen_dc, VERTRES) as u32;
            let _ = ReleaseDC(None, screen_dc);
            (w, h)
        };

        let mut device: Option<ID3D11Device> = None;
        let mut context: Option<ID3D11DeviceContext> = None;
        let mut level = D3D_FEATURE_LEVEL_11_0;

        unsafe {
            D3D11CreateDevice(
                None,
                D3D_DRIVER_TYPE_HARDWARE,
                None::<&HMODULE>,
                D3D11_CREATE_DEVICE_BGRA_SUPPORT,
                None,
                7,
                Some(&mut device as *mut _),
                Some(&mut level as *mut _),
                Some(&mut context as *mut _),
            )
        }
        .context("D3D11CreateDevice")?;

        let device = device.unwrap();
        let context = context.unwrap();

        let tex_desc = D3D11_TEXTURE2D_DESC {
            Width: width,
            Height: height,
            MipLevels: 1,
            ArraySize: 1,
            Format: DXGI_FORMAT_B8G8R8A8_UNORM,
            SampleDesc: DXGI_SAMPLE_DESC {
                Count: 1,
                Quality: 0,
            },
            Usage: D3D11_USAGE_DYNAMIC,
            BindFlags: D3D11_BIND_SHADER_RESOURCE.0 as u32,
            CPUAccessFlags: D3D11_CPU_ACCESS_WRITE.0 as u32,
            MiscFlags: 0,
        };
        let mut cached: Option<ID3D11Texture2D> = None;
        unsafe {
            device.CreateTexture2D(&tex_desc, None, Some(&mut cached as *mut _))?;
        }
        let cached = cached.context("CreateTexture2D")?;

        let cap = Self {
            device,
            context,
            backend: Backend::Gdi,
            cached,
            width,
            height,
        };
        cap.do_gdi_capture()?;
        Ok(cap)
    }

    pub fn acquire_frame(&mut self) -> Result<ID3D11Texture2D> {
        match &self.backend {
            Backend::Duplication(dup) => {
                let mut info = DXGI_OUTDUPL_FRAME_INFO::default();
                let mut resource = None;

                unsafe {
                    dup.AcquireNextFrame(0, &mut info, &mut resource)?;
                }

                if let Some(res) = resource {
                    let src: ID3D11Texture2D = res.cast()?;
                    unsafe { self.context.CopyResource(&self.cached, &src) };
                    unsafe { dup.ReleaseFrame()? };
                }
            }
            Backend::Gdi => {
                self.do_gdi_capture()?;
            },
        }

        Ok(self.cached.clone())
    }

    fn do_gdi_capture(&self) -> Result<()> {
        unsafe {
            let screen_dc = GetDC(None);
            if screen_dc.0.is_null() {
                anyhow::bail!("GetDC failed");
            }
            let mem_dc = CreateCompatibleDC(screen_dc);
            if mem_dc.0.is_null() {
                let _ = ReleaseDC(None, screen_dc);
                anyhow::bail!("CreateCompatibleDC failed");
            }
            let bitmap =
                CreateCompatibleBitmap(screen_dc, self.width as i32, self.height as i32);
            if bitmap.0.is_null() {
                let _ = DeleteDC(mem_dc);
                let _ = ReleaseDC(None, screen_dc);
                anyhow::bail!("CreateCompatibleBitmap failed");
            }
            let old = SelectObject(mem_dc, bitmap);

            if BitBlt(
                mem_dc,
                0,
                0,
                self.width as i32,
                self.height as i32,
                screen_dc,
                0,
                0,
                SRCCOPY,
            )
            .is_err()
            {
                let _ = SelectObject(mem_dc, old);
                let _ = DeleteObject(bitmap);
                let _ = DeleteDC(mem_dc);
                let _ = ReleaseDC(None, screen_dc);
                anyhow::bail!("BitBlt failed");
            }

            let mut bmi = BITMAPINFO {
                bmiHeader: BITMAPINFOHEADER {
                    biSize: mem::size_of::<BITMAPINFOHEADER>() as u32,
                    biWidth: self.width as i32,
                    biHeight: -(self.height as i32),
                    biPlanes: 1,
                    biBitCount: 32,
                    biCompression: 0,
                    biSizeImage: 0,
                    biXPelsPerMeter: 0,
                    biYPelsPerMeter: 0,
                    biClrUsed: 0,
                    biClrImportant: 0,
                },
                bmiColors: [RGBQUAD::default(); 1],
            };

            let row_bytes = (self.width * 4) as usize;
            let mut pixels: Vec<u8> =
                vec![0u8; row_bytes * self.height as usize];

            let lines = GetDIBits(
                mem_dc,
                bitmap,
                0,
                self.height,
                Some(pixels.as_mut_ptr() as *mut std::ffi::c_void),
                &mut bmi,
                DIB_RGB_COLORS,
            );

            let _ = SelectObject(mem_dc, old);
            let _ = DeleteObject(bitmap);
            let _ = DeleteDC(mem_dc);
            let _ = ReleaseDC(None, screen_dc);

            if lines == 0 {
                anyhow::bail!("GetDIBits failed");
            }

            let mut mapped = D3D11_MAPPED_SUBRESOURCE::default();
            self.context.Map(
                &self.cached,
                0,
                D3D11_MAP_WRITE_DISCARD,
                0,
                Some(&mut mapped as *mut _),
            )?;

            let dst = std::slice::from_raw_parts_mut(
                mapped.pData as *mut u8,
                mapped.RowPitch as usize * self.height as usize,
            );
            for row in 0..self.height as usize {
                let src_offset = row * row_bytes;
                let dst_offset = row * mapped.RowPitch as usize;
                dst[dst_offset..dst_offset + row_bytes]
                    .copy_from_slice(&pixels[src_offset..src_offset + row_bytes]);
            }

            self.context.Unmap(&self.cached, 0);
        }

        Ok(())
    }

    pub fn size(&self) -> (u32, u32) {
        (self.width, self.height)
    }
}

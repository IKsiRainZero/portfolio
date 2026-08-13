use anyhow::Result;
use windows::core::Interface;
use windows::Win32::Foundation::{BOOL, HWND};
use windows::Win32::Graphics::Direct3D11::*;
use windows::Win32::Graphics::Dxgi::*;
use windows::Win32::Graphics::Dxgi::Common::*;

pub struct Renderer {
    context: ID3D11DeviceContext,
    swapchain: IDXGISwapChain,
}

impl Renderer {
    pub fn new(
        hwnd: *mut std::ffi::c_void,
        device: &ID3D11Device,
        context: ID3D11DeviceContext,
        width: u32,
        height: u32,
    ) -> Result<Self> {
        let factory: IDXGIFactory1 = unsafe { CreateDXGIFactory1() }?;

        let swap_desc = DXGI_SWAP_CHAIN_DESC {
            BufferDesc: DXGI_MODE_DESC {
                Width: width,
                Height: height,
                RefreshRate: DXGI_RATIONAL {
                    Numerator: 60,
                    Denominator: 1,
                },
                Format: DXGI_FORMAT_B8G8R8A8_UNORM,
                ScanlineOrdering: DXGI_MODE_SCANLINE_ORDER_UNSPECIFIED,
                Scaling: DXGI_MODE_SCALING_UNSPECIFIED,
            },
            SampleDesc: DXGI_SAMPLE_DESC {
                Count: 1,
                Quality: 0,
            },
            BufferUsage: DXGI_USAGE_RENDER_TARGET_OUTPUT,
            BufferCount: 2,
            OutputWindow: HWND(hwnd),
            Windowed: BOOL(1),
            SwapEffect: DXGI_SWAP_EFFECT_FLIP_DISCARD,
            Flags: 0,
        };

        let factory: IDXGIFactory = factory.cast()?;
        let mut swapchain: Option<IDXGISwapChain> = None;
        unsafe {
            factory
                .CreateSwapChain(device, &swap_desc, &mut swapchain as *mut _)
                .ok()?;
        }
        let swapchain = swapchain.unwrap();

        Ok(Self { context, swapchain })
    }

    pub fn render(&self, texture: &ID3D11Texture2D) -> Result<()> {
        unsafe {
            let backbuffer: ID3D11Texture2D = self.swapchain.GetBuffer(0)?;
            self.context.CopyResource(&backbuffer, texture);
            self.swapchain.Present(1, DXGI_PRESENT(0)).ok()?;
        }
        Ok(())
    }
}

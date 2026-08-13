use anyhow::{Context, Result};
use std::ffi::CString;
use std::mem;
use windows::core::PCSTR;
use windows::Win32::Graphics::Direct3D::*;
use windows::Win32::Graphics::Direct3D::Fxc::*;
use windows::Win32::Graphics::Direct3D11::*;
use windows::Win32::Graphics::Dxgi::Common::*;

#[repr(C)]
#[derive(Clone, Copy)]
struct BlackHoleParams {
    resolution: [f32; 2],
    m: f32,
    a_spin: f32,
    theta_obs: f32,
    fov_scale: f32,
    bh_pos: [f32; 2],
    disk_inner: f32,
    disk_outer: f32,
    r_obs: f32,
    time: f32,
    disk_roll: f32,
    gravity_mode: f32,
    gravity_time: f32,
    _pad3: f32,
    disk_tint: [f32; 3],
    _pad_tint: f32,
    lens_strength: f32,
    _pad_lens: f32,
    _pad_lens2: f32,
    _pad_lens3: f32,
}

pub struct BlackholeEffect {
    context: ID3D11DeviceContext,
    cs: ID3D11ComputeShader,
    output: ID3D11Texture2D,
    input_srv: ID3D11ShaderResourceView,
    output_uav: ID3D11UnorderedAccessView,
    _frozen: ID3D11Texture2D,
    frozen_uav: ID3D11UnorderedAccessView,
    cb: ID3D11Buffer,
    width: u32,
    height: u32,
    pub a_spin: f32,
    pub disk_inner: f32,
    pub disk_outer: f32,
    pub theta_obs_offset: f32,
    pub disk_roll: f32,
    pub disk_tint: [f32; 3],
    pub lens_strength: f32,
    pub gravity_mode: bool,
    pub gravity_time: f32,
    // random walk state
    rw_from_x: f32,
    rw_from_y: f32,
    rw_to_x: f32,
    rw_to_y: f32,
    rw_seg_start: f32,
    rw_seg_dur: f32,
    rw_seed: u64,
}

impl BlackholeEffect {
    pub fn new(
        device: &ID3D11Device,
        context: ID3D11DeviceContext,
        input_texture: &ID3D11Texture2D,
        width: u32,
        height: u32,
    ) -> Result<Self> {
        let hlsl = include_str!("blackhole.hlsl");
        let hlsl_bytes = hlsl.as_bytes();

        let mut code: Option<ID3DBlob> = None;
        let mut errors: Option<ID3DBlob> = None;

        let entry = CString::new("main").unwrap();
        let target = CString::new("cs_5_0").unwrap();

        let hr = unsafe {
            D3DCompile(
                hlsl_bytes.as_ptr() as *const std::ffi::c_void,
                hlsl_bytes.len(),
                PCSTR::null(),
                None,
                None::<&ID3DInclude>,
                PCSTR(entry.as_ptr() as *const u8),
                PCSTR(target.as_ptr() as *const u8),
                D3DCOMPILE_SKIP_OPTIMIZATION,
                0,
                &mut code as *mut _,
                Some(&mut errors as *mut _),
            )
        };

        if let Some(ref err_blob) = errors {
            let err_ptr = unsafe { err_blob.GetBufferPointer() };
            let err_len = unsafe { err_blob.GetBufferSize() };
            if err_len > 0 {
                let err_msg = unsafe {
                    std::str::from_utf8_unchecked(std::slice::from_raw_parts(
                        err_ptr as *const u8,
                        err_len,
                    ))
                };
                if hr.is_err() {
                    anyhow::bail!("HLSL compile error:\n{}", err_msg);
                }
            }
        }

        hr?;
        let code = code.context("D3DCompile returned no bytecode")?;
        let bytecode = unsafe {
            std::slice::from_raw_parts(code.GetBufferPointer() as *const u8, code.GetBufferSize())
        };

        let mut cs: Option<ID3D11ComputeShader> = None;
        unsafe {
            device.CreateComputeShader(
                bytecode,
                None::<&ID3D11ClassLinkage>,
                Some(&mut cs as *mut _),
            )?;
        }
        let cs = cs.context("CreateComputeShader")?;

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
            Usage: D3D11_USAGE_DEFAULT,
            BindFlags: D3D11_BIND_UNORDERED_ACCESS.0 as u32,
            CPUAccessFlags: 0,
            MiscFlags: 0,
        };
        let mut output: Option<ID3D11Texture2D> = None;
        unsafe {
            device.CreateTexture2D(&tex_desc, None, Some(&mut output as *mut _))?;
        }
        let output = output.context("CreateTexture2D for output")?;

        let mut input_srv: Option<ID3D11ShaderResourceView> = None;
        unsafe {
            device.CreateShaderResourceView(
                input_texture,
                None,
                Some(&mut input_srv as *mut _),
            )?;
        }
        let input_srv = input_srv.context("CreateShaderResourceView")?;

        let mut output_uav: Option<ID3D11UnorderedAccessView> = None;
        unsafe {
            device.CreateUnorderedAccessView(&output, None, Some(&mut output_uav as *mut _))?;
        }
        let output_uav = output_uav.context("CreateUnorderedAccessView")?;

        // Frozen layer: persistent accumulation buffer for gravity-mode capture
        let mut frozen: Option<ID3D11Texture2D> = None;
        unsafe {
            device.CreateTexture2D(&tex_desc, None, Some(&mut frozen as *mut _))?;
        }
        let frozen = frozen.context("CreateTexture2D for frozen")?;
        let mut frozen_uav: Option<ID3D11UnorderedAccessView> = None;
        unsafe {
            device.CreateUnorderedAccessView(&frozen, None, Some(&mut frozen_uav as *mut _))?;
        }
        let frozen_uav = frozen_uav.context("CreateUnorderedAccessView for frozen")?;

        let cb_size = mem::size_of::<BlackHoleParams>() as u32;
        let cb_desc = D3D11_BUFFER_DESC {
            ByteWidth: cb_size,
            Usage: D3D11_USAGE_DYNAMIC,
            BindFlags: D3D11_BIND_CONSTANT_BUFFER.0 as u32,
            CPUAccessFlags: D3D11_CPU_ACCESS_WRITE.0 as u32,
            MiscFlags: 0,
            StructureByteStride: 0,
        };
        let mut cb: Option<ID3D11Buffer> = None;
        unsafe {
            device.CreateBuffer(&cb_desc, None, Some(&mut cb as *mut _))?;
        }
        let cb = cb.context("CreateBuffer for CB")?;

        Ok(Self {
            context,
            cs,
            output,
            input_srv,
            output_uav,
            _frozen: frozen,
            frozen_uav,
            cb,
            width,
            height,
            a_spin: 0.9,
            disk_inner: 2.3,
            disk_outer: 12.0,
            theta_obs_offset: 0.0,
            disk_roll: 0.35,
            disk_tint: [1.0, 1.0, 1.0],
            lens_strength: 1.0,
            gravity_mode: false,
            gravity_time: 0.0,
            rw_from_x: 0.5,
            rw_from_y: 0.5,
            rw_to_x: 0.5,
            rw_to_y: 0.5,
            rw_seg_start: 0.0,
            rw_seg_dur: 0.1,
            rw_seed: 0xDEAD_BEEF_1234_5678,
        })
    }

    pub fn process(&mut self, time: f32) -> Result<ID3D11Texture2D> {
        // ── random walk BH position ──
        if time >= self.rw_seg_start + self.rw_seg_dur {
            self.rw_from_x = self.rw_to_x;
            self.rw_from_y = self.rw_to_y;
            // LCG step
            let s = self.rw_seed.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407);
            self.rw_to_x = 0.12 + 0.76 * ((s >> 16) as f32 / (1u64 << 48) as f32);
            let s = s.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407);
            self.rw_to_y = 0.12 + 0.76 * ((s >> 16) as f32 / (1u64 << 48) as f32);
            let s = s.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407);
            self.rw_seg_dur = 1.5 + 3.5 * ((s >> 16) as f32 / (1u64 << 48) as f32);
            self.rw_seg_start = time;
            self.rw_seed = s;
        }
        let t_seg = ((time - self.rw_seg_start) / self.rw_seg_dur).min(1.0);
        let t_smooth = t_seg * t_seg * (3.0 - 2.0 * t_seg); // smoothstep
        let bh_x = self.rw_from_x + (self.rw_to_x - self.rw_from_x) * t_smooth;
        let bh_y = self.rw_from_y + (self.rw_to_y - self.rw_from_y) * t_smooth;

        // BH grows over 120s as it "consumes": fov_scale 110 → 50
        let t_grow = (time / 120.0).min(1.0);
        let fov_scale = 110.0 - t_grow * 60.0;

        // Wobble + manual offset — two frequencies for erratic feel
        let theta_obs = 1.20 + self.theta_obs_offset
            + 0.40 * (time * 0.25).sin()
            + 0.15 * (time * 0.73).sin();

        // Disk roll: time-varying + manual offset
        let disk_roll = self.disk_roll
            + 0.12 * (time * 0.17).sin()
            + 0.06 * (time * 0.61).sin();

        // Gravity mode: accumulate time while active
        if self.gravity_mode {
            self.gravity_time += 0.016; // ~60fps increment
        } else {
            self.gravity_time = 0.0;
        }
        let gravity_mode = if self.gravity_mode { 1.0_f32 } else { 0.0_f32 };

        let params = BlackHoleParams {
            resolution: [self.width as f32, self.height as f32],
            m: 1.0,
            a_spin: self.a_spin,
            theta_obs,
            fov_scale,
            bh_pos: [bh_x, bh_y],
            disk_inner: self.disk_inner,
            disk_outer: self.disk_outer,
            r_obs: 500.0,
            time,
            disk_roll,
            gravity_mode,
            gravity_time: self.gravity_time,
            _pad3: 0.0,
            disk_tint: self.disk_tint,
            _pad_tint: 0.0,
            lens_strength: self.lens_strength,
            _pad_lens: 0.0,
            _pad_lens2: 0.0,
            _pad_lens3: 0.0,
        };

        unsafe {
            let mut mapped = D3D11_MAPPED_SUBRESOURCE::default();
            self.context.Map(
                &self.cb,
                0,
                D3D11_MAP_WRITE_DISCARD,
                0,
                Some(&mut mapped as *mut _),
            )?;
            std::ptr::copy_nonoverlapping(
                &params as *const BlackHoleParams as *const std::ffi::c_void,
                mapped.pData,
                mem::size_of::<BlackHoleParams>(),
            );
            self.context.Unmap(&self.cb, 0);

            self.context.CSSetShader(&self.cs, None);
            let srvs = [Some(self.input_srv.clone())];
            self.context.CSSetShaderResources(0, Some(&srvs));
            let uavs: [Option<ID3D11UnorderedAccessView>; 2] =
                [Some(self.output_uav.clone()), Some(self.frozen_uav.clone())];
            self.context
                .CSSetUnorderedAccessViews(0, 2, Some(uavs.as_ptr()), None);
            self.context
                .CSSetConstantBuffers(0, Some(&[Some(self.cb.clone())]));

            let gx = (self.width + 15) / 16;
            let gy = (self.height + 15) / 16;
            self.context.Dispatch(gx, gy, 1);

            // unbind to avoid D3D debug layer warnings on subsequent CopyResource
            let null_cs = None::<&ID3D11ComputeShader>;
            self.context.CSSetShader(null_cs, None);
            let null_srvs: [Option<ID3D11ShaderResourceView>; 1] = [None];
            self.context.CSSetShaderResources(0, Some(&null_srvs));
            self.context.CSSetUnorderedAccessViews(0, 0, None, None);
            let null_cbs: [Option<ID3D11Buffer>; 1] = [None];
            self.context.CSSetConstantBuffers(0, Some(&null_cbs));
        }

        Ok(self.output.clone())
    }
}

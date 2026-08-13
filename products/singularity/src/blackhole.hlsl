#define PI 3.14159265358979323846
#define MAX_STEPS 600
#define H_MIN 0.0001
#define H_MAX 2.0
#define EPS 0.005

cbuffer BlackHoleParams : register(b0) {
    float2 resolution;
    float  M;
    float  a_spin;
    float  theta_obs;
    float  fov_scale;
    float2 bh_pos;
    float  disk_inner;
    float  disk_outer;
    float  r_obs;
    float  time;
    float  disk_roll;
    float  gravity_mode;
    float  gravity_time;
    float  _pad_new;
    float3 disk_tint;
    float  _pad_tint;
    float  lens_strength;
    float  _pad_lens;
}

Texture2D<float4> InputTexture : register(t0);
RWTexture2D<float4> OutputTexture : register(u0);
RWTexture2D<float4> FrozenLayer : register(u1);

static const float DISK_GAIN     = 2.2;
static const float DISK_OPACITY  = 0.50;
static const float DISK_BEAM     = 2.8;
static const float DISK_CONTRAST = 0.5;
static const float DISK_WIND     = 7.0;
static const float DISK_SPEED    = 5.0;
static const float DISK_HALF_THICKNESS = 0.10;

// ─── metric helpers ───

float delta(float r) {
    return r * r - 2.0 * M * r + a_spin * a_spin;
}

float r_horizon() {
    float disc = M * M - a_spin * a_spin;
    return disc > 0.0 ? M + sqrt(disc) : M;
}

float radial_R(float r, float lambda, float q_sq) {
    float P = r * r + a_spin * a_spin - a_spin * lambda;
    return P * P - delta(r) * (q_sq + (lambda - a_spin) * (lambda - a_spin));
}

float theta_T(float theta, float lambda, float q_sq) {
    float st = sin(theta);
    float ct = cos(theta);
    float a2 = a_spin * a_spin;
    return q_sq + a2 * ct * ct - lambda * lambda * ct * ct / (st * st);
}

float dphi_dual(float r, float theta, float lambda) {
    float P = r * r + a_spin * a_spin - a_spin * lambda;
    float st = sin(theta);
    return a_spin * P / delta(r) + lambda / (st * st) - a_spin;
}

float kepler_omega(float r) {
    float s = sqrt(M);
    return s / (r * sqrt(r) + a_spin * s);
}

float disk_ut(float r) {
    float Omega = kepler_omega(r);
    float g_tt = -(1.0 - 2.0 * M / r);
    float g_tp = -2.0 * a_spin * M / r;
    float g_pp = r * r + a_spin * a_spin + 2.0 * a_spin * a_spin * M / r;
    float denom = g_tt + 2.0 * Omega * g_tp + Omega * Omega * g_pp;
    if (denom >= 0.0) return 1000.0;
    return 1.0 / sqrt(-denom);
}

float doppler_g(float r, float lambda) {
    float Omega = kepler_omega(r);
    float ut = disk_ut(r);
    return 1.0 / (ut * (1.0 - lambda * Omega));
}

// ─── noise ───

float hash21(float2 p) {
    p = frac(p * float2(234.34, 435.345));
    p += dot(p, p + 34.23);
    return frac(p.x * p.y);
}

float mod_glsl(float x, float y) { return x - y * floor(x / y); }

float vnoiseWrapY(float2 p, float perY) {
    float2 i = floor(p);
    float2 f = frac(p);
    f = f * f * (3.0 - 2.0 * f);
    float y0 = mod_glsl(i.y, perY);
    float y1 = mod_glsl(i.y + 1.0, perY);
    return lerp(
        lerp(hash21(float2(i.x, y0)), hash21(float2(i.x + 1.0, y0)), f.x),
        lerp(hash21(float2(i.x, y1)), hash21(float2(i.x + 1.0, y1)), f.x),
        f.y);
}

// ─── starfield ───

float3 stars(float3 d) {
    float2 sph = float2(atan2(d.x, -d.z), asin(clamp(d.y, -1.0, 1.0)));
    float2 g = sph * 40.0;
    float2 id = floor(g);
    float h = hash21(id);
    if (h < 0.92) return float3(0.0, 0.0, 0.0);
    float2 f = frac(g) - 0.5;
    float2 off = (float2(hash21(id + 17.3), hash21(id + 31.7)) - 0.5) * 0.7;
    float spark = smoothstep(0.10, 0.0, length(f - off));
    float tw = 0.7 + 0.3 * sin(time * (0.5 + 2.0 * hash21(id + 5.1)) + 40.0 * h);
    float3 tint = lerp(float3(1.0, 0.82, 0.60), float3(0.75, 0.85, 1.0), hash21(id + 2.9));
    return tint * spark * tw * ((h - 0.92) / 0.08);
}

// ─── RK4 for r, θ, φ ───

float safe_sqrt(float x) {
    return sqrt(max(0.0, x));
}

struct GeoState {
    float r;
    float theta;
    float phi;
    float sign_r;
    float sign_theta;
};

float adaptive_h(float r, float theta, float lambda, float q_sq) {
    float v_approx = max(r * r, 1.0);
    float h_r = clamp(0.03 * r / v_approx, H_MIN, H_MAX);
    // Prevent pole overshoot: limit θ step to half the distance to nearest pole.
    // Apply AFTER r-clamp so H_MIN doesn't override the θ limit near poles.
    float dp = min(theta, PI - theta);
    float st = max(sin(theta), 1e-10);
    float v_theta = sqrt(max(0.0, q_sq + a_spin * a_spin + lambda * lambda / (st * st)));
    float max_dtheta = max(dp * 0.5, 1e-7);
    float h = h_r;
    if (v_theta > 0.0) {
        h = min(h, max_dtheta / v_theta);
    }
    return max(h, 1e-8);
}

void rk4_step(inout GeoState s, float lambda, float q_sq) {
    float h = adaptive_h(s.r, s.theta, lambda, q_sq);

    float v_r = s.sign_r * safe_sqrt(radial_R(s.r, lambda, q_sq));
    float v_theta = s.sign_theta * safe_sqrt(theta_T(s.theta, lambda, q_sq));
    float v_phi = dphi_dual(s.r, s.theta, lambda);

    float k1_r = v_r * h;
    float k1_theta = v_theta * h;
    float k1_phi = v_phi * h;

    float r2 = s.r + 0.5 * k1_r;
    float t2 = clamp(s.theta + 0.5 * k1_theta, 1e-10, PI - 1e-10);
    float v_r2 = s.sign_r * safe_sqrt(radial_R(r2, lambda, q_sq));
    float v_theta2 = s.sign_theta * safe_sqrt(theta_T(t2, lambda, q_sq));
    float v_phi2 = dphi_dual(r2, t2, lambda);
    float k2_r = v_r2 * h;
    float k2_theta = v_theta2 * h;
    float k2_phi = v_phi2 * h;

    float r3 = s.r + 0.5 * k2_r;
    float t3 = clamp(s.theta + 0.5 * k2_theta, 1e-10, PI - 1e-10);
    float v_r3 = s.sign_r * safe_sqrt(radial_R(r3, lambda, q_sq));
    float v_theta3 = s.sign_theta * safe_sqrt(theta_T(t3, lambda, q_sq));
    float v_phi3 = dphi_dual(r3, t3, lambda);
    float k3_r = v_r3 * h;
    float k3_theta = v_theta3 * h;
    float k3_phi = v_phi3 * h;

    float r4 = s.r + k3_r;
    float t4 = clamp(s.theta + k3_theta, 1e-10, PI - 1e-10);
    float v_r4 = s.sign_r * safe_sqrt(radial_R(r4, lambda, q_sq));
    float v_theta4 = s.sign_theta * safe_sqrt(theta_T(t4, lambda, q_sq));
    float v_phi4 = dphi_dual(r4, t4, lambda);
    float k4_r = v_r4 * h;
    float k4_theta = v_theta4 * h;
    float k4_phi = v_phi4 * h;

    float prev_r = s.r;
    float prev_theta = s.theta;
    float prev_phi = s.phi;

    s.r += (k1_r + 2.0 * k2_r + 2.0 * k3_r + k4_r) / 6.0;
    s.theta += (k1_theta + 2.0 * k2_theta + 2.0 * k3_theta + k4_theta) / 6.0;
    s.phi   += (k1_phi + 2.0 * k2_phi + 2.0 * k3_phi + k4_phi) / 6.0;

    // Safety clamp: keep θ strictly inside (0, π). Revert all coords on violation.
    if (s.theta <= 1e-8 || s.theta >= PI - 1e-8) {
        s.r = prev_r;
        s.theta = prev_theta;
        s.phi = prev_phi;
        s.sign_theta *= -1.0;
    }

    float T_cur = theta_T(s.theta, lambda, q_sq);
    if (T_cur < 0.0) {
        s.sign_theta *= -1.0;
        s.theta = prev_theta;
        s.phi = prev_phi;
        s.r = prev_r;
    }

    float R_cur = radial_R(s.r, lambda, q_sq);
    if (R_cur < 0.0 && s.r > r_horizon() + 0.01 * M) {
        s.sign_r *= -1.0;
        s.r = prev_r;
    }
}

// ─── main ───

[numthreads(16, 16, 1)]
void main(uint3 dtid : SV_DispatchThreadID) {
    if (dtid.x >= (uint)resolution.x || dtid.y >= (uint)resolution.y) return;

    float cx = resolution.x * bh_pos.x;
    float cy = resolution.y * bh_pos.y;
    float alpha = ((float)dtid.x - cx) * fov_scale / resolution.x;
    float beta  = ((float)dtid.y - cy) * fov_scale / resolution.y;

    // Disk roll: rotate the impact parameter plane around line of sight
    float cr = cos(disk_roll);
    float sr = sin(disk_roll);
    float alpha_rot = alpha * cr - beta * sr;
    float beta_rot  = alpha * sr + beta * cr;

    float sin_obs = sin(theta_obs);
    float cos_obs = cos(theta_obs);
    float lambda = -alpha_rot * sin_obs;
    float q_sq = beta_rot * beta_rot + (alpha_rot * alpha_rot - a_spin * a_spin) * cos_obs * cos_obs;

    float b_screen = sqrt(alpha * alpha + beta * beta);
    float bmax = disk_outer + 3.0;
    float shadow_px = 5.2 * resolution.x / fov_scale;

    // Far-field fast path: analytic weak deflection for rays that can't hit the disk
    if (b_screen >= bmax) {
        float2 pixel_pos = float2(float(dtid.x), float(dtid.y));
        float2 dvec = pixel_pos - float2(cx, cy);
        float dist_px = length(dvec);

        if (dist_px > 1.0) {
            // Gravitational pull: active mode draws surrounding content toward the BH
            if (gravity_mode > 0.5 && gravity_time > 0.0) {
                float pull = gravity_time * 3.0 / (dist_px * 0.02 + 1.0);
                pixel_pos -= dvec * min(pull, 0.6);
                dvec = pixel_pos - float2(cx, cy);
                dist_px = length(dvec);
            }

            float b_eff = max(b_screen / lens_strength, 0.5);
            float deflect_px = shadow_px * 5.2 / b_eff;
            float2 dir = dvec / max(dist_px, 1.0);

            float ab = 0.035 * smoothstep(1.0, 2.0, b_screen / bmax);
            float3 bg_far;
            {
                float2 sp_r = pixel_pos - dir * deflect_px * (1.0 - ab);
                uint2 sc_r = (uint2)clamp(sp_r, float2(0.0, 0.0), resolution - 1.0);
                bg_far.r = InputTexture[sc_r].r;
            }
            {
                float2 sp_g = pixel_pos - dir * deflect_px;
                uint2 sc_g = (uint2)clamp(sp_g, float2(0.0, 0.0), resolution - 1.0);
                bg_far.g = InputTexture[sc_g].g;
            }
            {
                float2 sp_b = pixel_pos - dir * deflect_px * (1.0 + ab);
                uint2 sc_b = (uint2)clamp(sp_b, float2(0.0, 0.0), resolution - 1.0);
                bg_far.b = InputTexture[sc_b].b;
            }

            float3 d_ff = normalize(float3(-alpha, -beta, -r_obs));
            float3 star_ff = stars(d_ff) * 0.18;

            float ring3d_ff = exp(-0.5 * pow((b_screen - disk_inner * 1.5) / 0.5, 2.0));
            float sin_el_ff = beta_rot / max(b_screen, 0.01);
            float near_ff = smoothstep(-0.15, 0.3, sin_el_ff);
            float3 ring3d_col = disk_tint * ring3d_ff * near_ff * 0.7 * lens_strength;
            OutputTexture[dtid.xy] = float4(bg_far + star_ff + ring3d_col, 1.0);
        } else {
            OutputTexture[dtid.xy] = float4(0.0, 0.0, 0.0, 1.0);
        }
        return;
    }

    if (radial_R(r_obs, lambda, q_sq) < 0.0) {
        OutputTexture[dtid.xy] = float4(0.0, 0.0, 0.0, 1.0);
        return;
    }

    GeoState s;
    s.r = r_obs;
    s.theta = theta_obs;
    s.phi = 0.0;
    s.sign_r = -1.0;
    s.sign_theta = -1.0;

    float r_h = r_horizon();
    float3 emitc = float3(0.0, 0.0, 0.0);
    float trans = 1.0;
    float prev_phi = s.phi;
    bool captured = false;
    int steps = 0;
    int winding = 0;
    float r_min = r_obs;

    for (; steps < MAX_STEPS; steps++) {
        float prev_r = s.r;
        float prev_theta = s.theta;
        prev_phi = s.phi;
        rk4_step(s, lambda, q_sq);

        r_min = min(r_min, s.r);

        if (s.r <= r_h + EPS) {
            captured = true;
            break;
        }

        float halfpi = PI * 0.5;
        if ((prev_theta - halfpi) * (s.theta - halfpi) < 0.0) {
            winding++;
            if (trans > 0.02) {
            float frac = (halfpi - prev_theta) / (s.theta - prev_theta);
            float r_cross = prev_r + frac * (s.r - prev_r);
            if (r_cross >= disk_inner) {
                float phi_cross = prev_phi + frac * (s.phi - prev_phi);

                float band = smoothstep(disk_inner, disk_inner * 1.25, r_cross)
                           * exp(-pow(r_cross / (disk_outer * 0.72), 3.5));

                if (band > 0.01) {
                    float turns = phi_cross / (2.0 * PI);
                    float kep = pow(disk_inner / r_cross, 1.5);
                    float gloc = sqrt(max(1.0 - 1.5 / r_cross, 0.02));
                    float swirl = r_cross * DISK_WIND * 0.12 - time * kep * DISK_SPEED * gloc;
                    float streaks = vnoiseWrapY(float2(r_cross * 2.8, turns * 19.0 + swirl * 3.0), 19.0) * 0.65
                                  + vnoiseWrapY(float2(r_cross * 1.0, turns * 9.0 + swirl * 1.5 + 7.0), 9.0) * 0.35;
                    streaks = 0.35 + DISK_CONTRAST * streaks * streaks;

                    float g = doppler_g(r_cross, lambda);
                    g = clamp(g, 0.3, 3.5);

                    float dtheta = abs(s.theta - prev_theta);
                    float vert_factor = 1.0 + 1.5 * (1.0 - clamp(dtheta * 8.0, 0.0, 1.0));

                    float density = band * streaks * vert_factor;

                    // Gravitational lensing amplification for far-side disk images
                    float lens_boost = 1.0;
                    if (winding >= 2) {
                        float prox = exp(-(r_cross - disk_inner) * 0.35);
                        lens_boost = 1.0 + 6.0 * prox * exp(-float(winding-2) * 0.5);
                    }

                    float turb_s = 0.07 * pow(disk_inner / max(r_cross, disk_inner), 0.6);
                    float turb_r = (vnoiseWrapY(float2(r_cross * 3.5, phi_cross * 6.0 + time * 0.25), 8.0) - 0.5) * 2.0;
                    float turb_phi = (vnoiseWrapY(float2(r_cross * 2.8 + time * 0.18, phi_cross * 5.0 + 3.7), 11.0) - 0.5) * 2.0;

                    // Tidal differential rotation: inner disk leads outer (Keplerian shear)
                    float tidal = pow(disk_inner / max(r_cross, disk_inner), 1.5);
                    float phi_screen = phi_cross - disk_roll + tidal * 1.2 + turb_phi * turb_s * 0.6;
                    float r_eff = r_cross * (1.0 + turb_r * turb_s) * (1.0 - tidal * 0.15);
                    float r_px = r_eff * resolution.x / fov_scale;
                    float2 disk_uv = float2(cx, cy)
                                   + r_px * float2(cos(phi_screen), -sin(phi_screen));
                    disk_uv = clamp(disk_uv, float2(0.0, 0.0), resolution - 1.0);
                    float3 disk_content = InputTexture[(uint2)disk_uv].rgb;

                    // Radial density: fades toward outer edge, no hard cutoff
                    float r_dens = pow(disk_inner / max(r_cross, disk_inner), 1.2);
                    // Inner hot glow — fills empty desktop areas with thermal baseline
                    float inner_glow = exp(-(r_cross - disk_inner) * 0.5);
                    float3 content = lerp(disk_content, float3(1.0, 0.95, 0.82), inner_glow * 0.18);

                    // Gravitational redshift: closer to horizon → redder + dimmer
                    float grav_z = sqrt(max(1.0 - r_h / r_cross, 0.0));
                    float3 grav_shift = float3(1.0, lerp(0.6, 1.0, grav_z * grav_z), lerp(0.35, 1.0, grav_z));
                    float grav_dim = lerp(0.45, 1.0, grav_z);
                    content = content * grav_shift * grav_dim;

                    float dopp_bright = pow(g, DISK_BEAM);
                    float cs = (g - 1.0) * 0.35;
                    float3 dopp_col = clamp(float3(1.0 + cs * 0.4, 1.0 - abs(cs) * 0.2, 1.0 - cs * 0.4), 0.55, 1.65);
                    float3 disk_emit = content * dopp_col * dopp_bright * DISK_GAIN * lens_boost * r_dens;

                    emitc += trans * disk_emit;
                    trans *= 1.0 - clamp(DISK_OPACITY * density, 0.0, 1.0);

                    // Bright material ring: narrow emission spike for 3D front-passing illusion
                    float ring_r = disk_outer * 0.42;
                    float ring_spike = exp(-0.5 * pow((r_cross - ring_r) / 0.28, 2.0));
                    if (ring_spike > 0.005) {
                        float3 ring_emit = content * dopp_col * dopp_bright * DISK_GAIN * ring_spike * 14.0;
                        emitc += trans * ring_emit;
                        trans *= 1.0 - clamp(DISK_OPACITY * ring_spike * 0.3, 0.0, 0.1);
                    }

                    // Orbiting hot spot: bright blob near ISCO, relativistic beaming
                    float r_hot = disk_inner * 1.2;
                    float hot_omega = kepler_omega(r_hot);
                    float hot_phi0 = fmod(hot_omega * time, 2.0 * PI);
                    float hot_dr = abs(r_cross - r_hot);
                    float hot_dphi = abs(phi_cross - hot_phi0);
                    hot_dphi = min(hot_dphi, 2.0 * PI - hot_dphi);
                    float hot_sr = exp(-0.5 * pow(hot_dr / 0.15, 2.0));
                    float hot_sp = exp(-0.5 * pow(hot_dphi / 0.25, 2.0));
                    float hot_spike = hot_sr * hot_sp;
                    if (hot_spike > 0.02) {
                        float g_h = clamp(doppler_g(r_cross, lambda), 0.3, 4.0);
                        float dopp_h = pow(g_h, DISK_BEAM + 1.5);
                        float3 hot_emit = float3(1.0, 0.92, 0.65) * dopp_h * hot_spike * 6.0;
                        emitc += trans * hot_emit;
                        trans *= 1.0 - clamp(DISK_OPACITY * hot_spike * 0.4, 0.0, 0.12);
                    }

                    // Frozen layer: material captured near inner edge
                    if (gravity_mode > 0.5) {
                        float freeze = exp(-(r_cross - disk_inner) * 3.0);
                        float3 frozen_col = disk_content * float3(0.5, 0.08, 0.02); // deep redshift
                        FrozenLayer[dtid.xy] += float4(frozen_col * freeze * 0.004, 0.0);
                    }
                }
            } else if (r_cross > r_h && r_cross < disk_inner && winding >= 1) {
                float plunge_z = (r_cross - r_h) / max(disk_inner - r_h, 0.01);
                float plunge_dens = plunge_z * plunge_z;
                float plunge_grav = sqrt(max(1.0 - r_h / r_cross, 0.0));
                float3 plunge_col = lerp(float3(0.5, 0.1, 0.02), float3(1.0, 0.85, 0.4), plunge_grav * plunge_grav);
                float g_p = clamp(doppler_g(r_cross, lambda), 0.3, 3.5);
                float dopp_p = pow(g_p, 2.0);
                float3 plunge_emit = plunge_col * plunge_dens * plunge_grav * dopp_p * 0.6;
                emitc += trans * plunge_emit;
                trans *= 1.0 - clamp(DISK_OPACITY * plunge_dens * 0.12, 0.0, 0.25);
                if (gravity_mode > 0.5) {
                    float freeze_p = plunge_dens * exp(-(r_cross - r_h) * 1.5);
                    FrozenLayer[dtid.xy] += float4(plunge_col * freeze_p * 0.006, 0.0);
                }
            }
            } // if trans > 0.02
        } // equatorial crossing

        // Volumetric emission over finite disk thickness
        if (trans > 0.02 && s.r >= disk_inner) {
            float local_half = DISK_HALF_THICKNESS * pow(s.r / disk_inner, 0.35);
            float dmid = abs(s.theta - halfpi);
            if (dmid < local_half) {
                float vdens = exp(-0.5 * pow(dmid / (local_half * 0.45), 2.0));
                float vol_outer = exp(-pow(s.r / (disk_outer * 0.72), 3.5));
                float g_v = clamp(doppler_g(s.r, lambda), 0.3, 3.5);
                float beam_v = pow(g_v, DISK_BEAM);

                float turb_s_v = 0.07 * pow(disk_inner / max(s.r, disk_inner), 0.6);
                float turb_r_v = (vnoiseWrapY(float2(s.r * 3.5, s.phi * 6.0 + time * 0.25), 8.0) - 0.5) * 2.0;
                float turb_phi_v = (vnoiseWrapY(float2(s.r * 2.8 + time * 0.18, s.phi * 5.0 + 3.7), 11.0) - 0.5) * 2.0;

                float tidal_v = pow(disk_inner / max(s.r, disk_inner), 1.5);
                float phi_screen_v = s.phi - disk_roll + tidal_v * 1.2 + turb_phi_v * turb_s_v * 0.6;
                float r_turb_v = s.r * (1.0 + turb_r_v * turb_s_v) * (1.0 - tidal_v * 0.15);
                float r_px_v = r_turb_v * resolution.x / fov_scale;
                float2 disk_uv_v = float2(cx, cy)
                                 + r_px_v * float2(cos(phi_screen_v), -sin(phi_screen_v));
                disk_uv_v = clamp(disk_uv_v, float2(0.0, 0.0), resolution - 1.0);
                float3 disk_content_v = InputTexture[(uint2)disk_uv_v].rgb;

                float r_dens_v = pow(disk_inner / max(s.r, disk_inner), 1.2);
                float inner_glow_v = exp(-(s.r - disk_inner) * 0.5);
                float3 content_v = lerp(disk_content_v, float3(1.0, 0.95, 0.82), inner_glow_v * 0.18);

                float grav_z_v = sqrt(max(1.0 - r_h / s.r, 0.0));
                float3 grav_shift_v = float3(1.0, lerp(0.6, 1.0, grav_z_v * grav_z_v), lerp(0.35, 1.0, grav_z_v));
                float grav_dim_v = lerp(0.45, 1.0, grav_z_v);
                content_v = content_v * grav_shift_v * grav_dim_v;

                float cs_v = (g_v - 1.0) * 0.35;
                float3 dopp_col_v = clamp(float3(1.0 + cs_v * 0.4, 1.0 - abs(cs_v) * 0.2, 1.0 - cs_v * 0.4), 0.55, 1.65);

                emitc += trans * vdens * vol_outer * 0.18 * content_v * dopp_col_v * beam_v * DISK_GAIN * r_dens_v;
                trans *= 1.0 - clamp(DISK_OPACITY * vdens * vol_outer * 0.08, 0.0, 0.35);
            }
        }

        // Disk corona: disk light scattered by hot electrons (Rayleigh blue tint)
        if (trans > 0.02 && s.r > r_h) {
            float local_half_c = DISK_HALF_THICKNESS * pow(max(s.r, disk_inner) / disk_inner, 0.35);
            float dmid_c = abs(s.theta - halfpi);
            float corona_scale = local_half_c * 4.0;
            if (dmid_c < corona_scale) {
                float c_vert = exp(-0.5 * pow(dmid_c / (corona_scale * 0.38), 2.0));
                float c_rad = exp(-pow(s.r / (disk_outer * 0.65), 2.5));
                float tidal_c = pow(disk_inner / max(s.r, disk_inner), 1.5);
                float phi_cor = s.phi - disk_roll + tidal_c * 1.2;
                float r_px_c = s.r * resolution.x / fov_scale;
                float2 cor_uv = float2(cx, cy) + r_px_c * float2(cos(phi_cor), -sin(phi_cor));
                cor_uv = clamp(cor_uv, float2(0.0, 0.0), resolution - 1.0);
                float3 corona_src = InputTexture[(uint2)cor_uv].rgb;
                float3 corona_col = corona_src * float3(0.55, 0.72, 1.15);
                float g_c = clamp(doppler_g(s.r, lambda), 0.3, 3.5);
                float grav_z_c = sqrt(max(1.0 - r_h / s.r, 0.0));
                float grav_dim_c = lerp(0.35, 1.0, grav_z_c);
                emitc += trans * c_vert * c_rad * corona_col * pow(g_c, 1.5) * grav_dim_c * 0.10;
                trans *= 1.0 - clamp(0.016 * c_vert * c_rad, 0.0, 0.07);
            }
        }

        if (s.r > r_obs && s.sign_r > 0.0) break;
    }

    if (captured) {
        // ── Inner shadow: nested dark structure inside the main shadow ──
        float r_ph = r_h + 0.9;
        float inner_edge = smoothstep(r_h + 0.05, r_h + 0.35, r_min);
        float outer_edge = smoothstep(r_h, r_h + 1.8, r_min);

        float3 disk_col = (float3(1.0, 1.0, 1.0) - exp(-emitc * 1.4));
        float vis = 0.03 + inner_edge * 0.22;
        float3 col = disk_col * vis * outer_edge;

        OutputTexture[dtid.xy] = float4(col, 1.0);
        return;
    }

    // Gravitational lensing of background — 1/b radial deflection + chromatic aberration
    float2 pixel_pos = float2(float(dtid.x), float(dtid.y));
    float2 dvec = pixel_pos - float2(cx, cy);
    float dist_px = length(dvec);

    if (gravity_mode > 0.5 && gravity_time > 0.0) {
        float pull = gravity_time * 3.0 / (dist_px * 0.02 + 1.0);
        pixel_pos -= dvec * min(pull, 0.6);
        dvec = pixel_pos - float2(cx, cy);
        dist_px = length(dvec);
    }

    float b_eff = max(b_screen / lens_strength, 0.5);
    float deflect_px = shadow_px * 5.2 / b_eff;
    float2 dir = dist_px > 1.0 ? dvec / dist_px : float2(1.0, 0.0);

    float ab = 0.025 * smoothstep(1.0, 2.0, b_screen / bmax);
    float3 bg;
    {
        float2 sp_r = pixel_pos - dir * deflect_px * (1.0 - ab);
        uint2 sc_r = (uint2)clamp(sp_r, float2(0.0, 0.0), resolution - 1.0);
        bg.r = InputTexture[sc_r].r;
    }
    {
        float2 sp_g = pixel_pos - dir * deflect_px;
        uint2 sc_g = (uint2)clamp(sp_g, float2(0.0, 0.0), resolution - 1.0);
        bg.g = InputTexture[sc_g].g;
    }
    {
        float2 sp_b = pixel_pos - dir * deflect_px * (1.0 + ab);
        uint2 sc_b = (uint2)clamp(sp_b, float2(0.0, 0.0), resolution - 1.0);
        bg.b = InputTexture[sc_b].b;
    }

    // Starfield from exit direction
    float3 d_stars = float3(sin(s.theta) * cos(s.phi), sin(s.theta) * sin(s.phi), cos(s.theta));
    float3 star_bg = stars(d_stars) * 0.18;

    float3 col = (bg + star_bg) * trans + (float3(1.0, 1.0, 1.0) - exp(-emitc * 1.4));

    // ── sky-plane: winding≥1 rays see background from a different direction ──
    if (winding >= 1 && trans > 0.05) {
        float sin_exit = sin(s.theta);
        float cos_exit = cos(s.theta);
        // λ = -α_obs·sin(θ_obs) = -α_inf·sin(θ_exit)
        float alpha_inf = alpha_rot * sin_obs / max(sin_exit, 0.04);
        // β²_inf = q² - (α²_inf - a²)·cos²(θ_exit)
        float binf_sq = q_sq - (alpha_inf * alpha_inf - a_spin * a_spin) * cos_exit * cos_exit;
        if (binf_sq > 0.0) {
            // Sign of β flips with each equatorial crossing
            float beta_inf = sqrt(binf_sq);
            beta_inf *= (winding % 2 == 0) ? sign(beta_rot + 0.001) : -sign(beta_rot + 0.001);

            float d_a = alpha_inf - alpha_rot;
            float d_b = beta_inf - beta_rot;
            float2 sky_pos = pixel_pos + float2(d_a * resolution.x / fov_scale,
                                                  d_b * resolution.y / fov_scale);
            uint2 sky_uv = (uint2)clamp(sky_pos, float2(0.0, 0.0), resolution - 1.0);
            float3 bg_sky = InputTexture[sky_uv].rgb;

            // Lensing amplification: diverges near photon sphere, slow decay with winding
            float amp = exp(-float(winding) * 0.9) / max(r_min - r_h, 0.08);
            amp = min(amp, 1.0);

            col += bg_sky * amp * trans * 0.9;
        }
    }

    // Photon ring: narrow peak near photon sphere, decomposed by winding number.
    float r_ph = r_h + 0.9;
    float ring_w = 0.30 + 0.08 * lens_strength;
    float ring_dist = abs(r_min - r_ph);
    float ring = exp(-0.5 * pow(ring_dist / ring_w, 2.0));

    float screen_az = atan2(beta_rot, alpha_rot);
    float doppler_rim = 0.50 + 0.50 * sin(screen_az + a_spin * 1.2);

    // Base ring: grazing rays that never complete a full orbit (winding==0)
    float ring_bright = 1.2 * lens_strength * doppler_rim;

    // Sub-rings: rays completing 1, 2, 3, … half-orbits around the photon sphere.
    // Each sub-ring is geometrically closer to r_ph (exponential convergence) and dimmer.
    if (winding >= 1) {
        float r1 = r_h + 1.1;
        float w1 = ring_w * 0.52;
        ring_bright += 0.7 * lens_strength * exp(-0.5 * pow((r_min - r1) / max(w1, 0.03), 2.0)) * doppler_rim;
    }
    if (winding >= 2) {
        float r2 = r_h + 1.1 * exp(-1.0 * 0.55);
        float w2 = ring_w * 0.38;
        ring_bright += 0.28 * lens_strength * exp(-0.5 * pow((r_min - r2) / max(w2, 0.025), 2.0)) * doppler_rim;
    }
    if (winding >= 3) {
        float r3 = r_h + 1.1 * exp(-2.0 * 0.55);
        float w3 = ring_w * 0.26;
        ring_bright += 0.10 * lens_strength * exp(-0.5 * pow((r_min - r3) / max(w3, 0.018), 2.0)) * doppler_rim;
    }
    if (winding >= 4) {
        float r4 = r_h + 1.1 * exp(-3.0 * 0.55);
        float w4 = ring_w * 0.16;
        ring_bright += 0.04 * lens_strength * exp(-0.5 * pow((r_min - r4) / max(w4, 0.012), 2.0)) * doppler_rim;
    }
    if (winding >= 5) {
        float r5 = r_h + 1.1 * exp(-4.0 * 0.55);
        float w5 = ring_w * 0.11;
        ring_bright += 0.015 * lens_strength * exp(-0.5 * pow((r_min - r5) / max(w5, 0.008), 2.0)) * doppler_rim;
    }

    // Soft photon halo: wider glow around the ring complex
    float soft = exp(-ring_dist / (ring_w * 2.5)) * 0.08 * lens_strength;

    // Screen-space 3D ring accent: near side (bottom half) bright, far side dim
    float ring3d_r = disk_inner * 1.5;
    float ring3d = exp(-0.5 * pow((b_screen - ring3d_r) / 0.5, 2.0));
    float sin_elev = beta_rot / max(b_screen, 0.01);
    float near_side = smoothstep(-0.15, 0.3, sin_elev);
    col += disk_tint * ring3d * near_side * 0.7 * lens_strength;

    col += disk_tint * (ring * ring_bright + soft);

    // Gravitational chromatic aberration: differential light bending at photon ring.
    // Shorter wavelengths (blue) bend more, peaking slightly outward.
    // Longer wavelengths (red) bend less, peaking slightly inward.
    float ca_shift = ring_w * 0.22;
    float ring_ca_r = exp(-0.5 * pow((ring_dist + ca_shift) / ring_w, 2.0));
    float ring_ca_b = exp(-0.5 * pow((ring_dist - ca_shift) / ring_w, 2.0));
    float ca_r = (ring_ca_r - ring) * ring_bright * 0.25;
    float ca_b = (ring_ca_b - ring) * ring_bright * 0.25;
    col += float3(ca_r, 0.0, ca_b);

    // Frozen layer: material captured at event horizon, redshifted and time-dilated
    if (gravity_mode > 0.5) {
        float4 frozen = FrozenLayer[dtid.xy];
        col += frozen.rgb * 0.35; // subtle blend — frozen material is heavily redshifted
        FrozenLayer[dtid.xy] = frozen * 0.998; // very slow decay
    }

    OutputTexture[dtid.xy] = float4(col, 1.0);
}

'use client';

import React, { type ComponentProps, useMemo } from 'react';
import { type VariantProps, cva } from 'class-variance-authority';
import { type LocalAudioTrack, type RemoteAudioTrack } from 'livekit-client';
import { type AgentState, type TrackReferenceOrPlaceholder, useTrackVolume } from '@livekit/components-react';
import { ReactShaderToy } from '@/components/agents-ui/react-shader-toy';
import { cn } from '@/lib/shadcn/utils';

const DEFAULT_COLOR = '#00AEEF';

function hexToRgb(hexColor: string) {
  try {
    const rgbColor = hexColor.match(/^#([0-9a-fA-F]{2})([0-9a-fA-F]{2})([0-9a-fA-F]{2})$/);
    if (rgbColor) {
      const [, r, g, b] = rgbColor;
      return [r, g, b].map((c = '00') => parseInt(c, 16) / 255);
    }
  } catch (e) {}
  return [0, 0.68, 0.94]; // Default Blue
}

const shaderSource = `
// --- Math Helpers ---
mat2 rot(float a) {
    float s = sin(a), c = cos(a);
    return mat2(c, -s, s, c);
}

float sdCircle(vec2 p, float r) {
    return length(p) - r;
}

float sdLine(vec3 p, vec3 a, vec3 b) {
    vec3 pa = p - a, ba = b - a;
    float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0);
    return length(pa - ba * h);
}

// --- HUD Elements ---
float ring(vec2 uv, float r, float width, float speed) {
    float d = abs(length(uv) - r) - width;
    float angle = atan(uv.y, uv.x);
    float pattern = step(0.5, fract(angle * 10.0 / (r * 5.0) + iTime * speed));
    return smoothstep(0.01, 0.0, d) * pattern;
}

// --- Icosahedron (D20) Wireframe ---
float sdIcosahedronWire(vec3 p, float scale) {
    // Pre-calculated normalized coordinates for Icosahedron vertices
    float a = 0.5257311121 * scale;
    float b = 0.8506508084 * scale;
    
    vec3 v[12];
    v[0] = vec3(0, a, b);   v[1] = vec3(0, a, -b);  v[2] = vec3(0, -a, b);  v[3] = vec3(0, -a, -b);
    v[4] = vec3(a, b, 0);   v[5] = vec3(a, -b, 0);  v[6] = vec3(-a, b, 0);  v[7] = vec3(-a, -b, 0);
    v[8] = vec3(b, 0, a);   v[9] = vec3(b, 0, -a);  v[10] = vec3(-b, 0, a); v[11] = vec3(-b, 0, -a);

    float d = 1e10;
    float d_points = 1e10;
    
    // Edges (Approx 30 edges)
    // Using simple loops with constant bounds for WebGL compatibility
    for(int i=0; i<12; i++) {
        vec3 vi = v[i];
        d_points = min(d_points, length(p - vi) - 0.015);
        for(int j=0; j<12; j++) {
            // Standard loop header and j > i check to avoid redefinition error
            if(j > i) {
                vec3 vj = v[j];
                if(length(vi - vj) < 1.1 * scale) {
                    d = min(d, sdLine(p, vi, vj) - 0.002);
                }
            }
        }
    }
    return min(d, d_points);
}

float map(vec3 p) {
    float speedMult = (uState == 2.0) ? 2.5 : (uState == 0.0 ? 0.2 : 0.8);
    float t = iTime * speedMult;
    
    vec3 p1 = p;
    p1.xy *= rot(t * 0.3);
    p1.yz *= rot(t * 0.2);
    
    return sdIcosahedronWire(p1, 0.6);
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;
    vec3 col = vec3(0.0);
    
    float vol = (uState == 3.0) ? uVolume : (uState == 1.0 ? 0.05 : 0.0);
    
    // 1. Background Grid/Nebula
    float grid = (sin(uv.x * 60.0) * sin(uv.y * 60.0)) * 0.01;
    col += uColor * grid;
    
    // 2. HUD Rings
    col += uColor * ring(uv, 0.42, 0.002, 0.15);
    col += uColor * ring(uv, 0.48, 0.001, -0.1);
    col += uColor * ring(uv, 0.58 + vol * 0.25, 0.003, 0.08) * 0.6;
    
    // 3. Central HUD Sphere/Circle
    float dist = length(uv);
    float circle = smoothstep(0.4, 0.398, dist) * smoothstep(0.38, 0.382, dist);
    col += uColor * circle * 0.4;
    
    // 4. Raymarched Icosahedron (D20 Wireframe)
    vec3 ro = vec3(0, 0, -2.5);
    vec3 rd = normalize(vec3(uv, 1.4));
    float t = 0.0;
    for(int i=0; i<40; i++) {
        vec3 p = ro + rd * t;
        float d = map(p);
        if(d < 0.001 || t > 4.0) break;
        t += d;
    }
    float coreGlow = 0.008 / (0.008 + map(ro + rd * t));
    col += uColor * coreGlow * (1.5 + vol * 5.0);
    
    // 5. Thin Data Beams (Ethereal)
    float angle = atan(uv.y, uv.x);
    float beams = pow(abs(sin(angle * 16.0 + iTime * 0.3)), 150.0);
    beams *= smoothstep(0.7, 0.4, dist);
    col += uColor * beams * 0.15 * (1.0 + vol * 8.0);
    
    // 6. Floating Particles
    float n = fract(sin(dot(uv + fract(iTime * 0.005), vec2(12.9898, 78.233))) * 43758.5453);
    if(n > 0.992) {
        float p = smoothstep(0.004, 0.0, length(uv - (n - 0.5) * 2.5));
        col += uColor * p * n * 0.4;
    }

    // 7. Overall Vignette and Glow
    col *= 1.3 - dist * 0.9;
    col += uColor * (0.03 / (dist + 0.05)) * (1.0 + vol);
    
    // Bloom/Tone map
    col = 1.0 - exp(-col * 2.8);
    
    fragColor = vec4(col, 1.0);
}
`;

export const AgentAudioVisualizerRafaelVariants = cva(['aspect-square'], {
  variants: {
    size: {
      icon: 'h-[24px]',
      sm: 'h-[56px]',
      md: 'h-[112px]',
      lg: 'h-[224px]',
      xl: 'h-[448px]',
    },
  },
  defaultVariants: {
    size: 'md',
  },
});

export interface AgentAudioVisualizerRafaelProps {
  size?: 'icon' | 'sm' | 'md' | 'lg' | 'xl';
  state?: AgentState;
  color?: string;
  audioTrack?: LocalAudioTrack | RemoteAudioTrack | TrackReferenceOrPlaceholder;
}

export function AgentAudioVisualizerRafael({
  size = 'lg',
  state = 'connecting',
  color = DEFAULT_COLOR,
  audioTrack,
  className,
  ...props
}: AgentAudioVisualizerRafaelProps & ComponentProps<'div'> & VariantProps<typeof AgentAudioVisualizerRafaelVariants>) {
  const rgbColor = useMemo(() => hexToRgb(color), [color]);
  const volume = useTrackVolume(audioTrack);

  const stateVal = useMemo(() => {
    switch (state) {
      case 'listening': return 1.0;
      case 'thinking': return 2.0;
      case 'speaking': return 3.0;
      default: return 0.0;
    }
  }, [state]);

  return (
    <div className={cn(AgentAudioVisualizerRafaelVariants({ size }), className)} {...props}>
      <ReactShaderToy
        fs={shaderSource}
        uniforms={{
          uColor: { type: '3fv', value: rgbColor },
          uVolume: { type: '1f', value: volume },
          uState: { type: '1f', value: stateVal },
        }}
        style={{ width: '100%', height: '100%' }}
      />
    </div>
  );
}

'use client';

import { type AgentState } from '@livekit/components-react';
import { useEffect, useRef } from 'react';
import { cn } from '@/lib/shadcn/utils';

interface CentralOrbProps {
  size?: number;
  state?: AgentState;
  isSpeaking?: boolean;
  audioAmplitude?: number;
  color?: string;
  className?: string;
}

type HudMode = 'connecting' | 'idle' | 'listening' | 'thinking' | 'speaking';

interface Rgb {
  r: number;
  g: number;
  b: number;
}

interface Point3 {
  x: number;
  y: number;
  z: number;
}

interface ProjectedPoint {
  x: number;
  y: number;
  z: number;
  scale: number;
}

interface HudState {
  amp: number;
  ringA: number;
  ringB: number;
  ringC: number;
  polyA: number;
  waveA: number;
  lastTime: number;
}

const DEFAULT_COLOR = '#00d8e6';
const PHI = (1 + Math.sqrt(5)) / 2;
const VERTEX_SCALE = 1 / Math.sqrt(1 + PHI * PHI);
const ICOSA_POINTS: Point3[] = [
  { x: -1, y: PHI, z: 0 },
  { x: 1, y: PHI, z: 0 },
  { x: -1, y: -PHI, z: 0 },
  { x: 1, y: -PHI, z: 0 },
  { x: 0, y: -1, z: PHI },
  { x: 0, y: 1, z: PHI },
  { x: 0, y: -1, z: -PHI },
  { x: 0, y: 1, z: -PHI },
  { x: PHI, y: 0, z: -1 },
  { x: PHI, y: 0, z: 1 },
  { x: -PHI, y: 0, z: -1 },
  { x: -PHI, y: 0, z: 1 },
].map((point) => ({
  x: point.x * VERTEX_SCALE,
  y: point.y * VERTEX_SCALE,
  z: point.z * VERTEX_SCALE,
}));

const ICOSA_EDGES: Array<[number, number]> = (() => {
  const edges: Array<[number, number]> = [];

  for (let i = 0; i < ICOSA_POINTS.length; i += 1) {
    for (let j = i + 1; j < ICOSA_POINTS.length; j += 1) {
      const a = ICOSA_POINTS[i];
      const b = ICOSA_POINTS[j];
      const distance = Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z);

      if (distance < 1.08) {
        edges.push([i, j]);
      }
    }
  }

  return edges;
})();

function parseColor(value = DEFAULT_COLOR): Rgb {
  const match = value.match(/^#?([0-9a-f]{6})$/i);
  const hex = match?.[1] ?? DEFAULT_COLOR.slice(1);

  return {
    r: parseInt(hex.slice(0, 2), 16),
    g: parseInt(hex.slice(2, 4), 16),
    b: parseInt(hex.slice(4, 6), 16),
  };
}

function rgba(color: Rgb, alpha: number) {
  return `rgba(${color.r}, ${color.g}, ${color.b}, ${Math.max(0, Math.min(alpha, 1))})`;
}

function getMode(state: AgentState | undefined, isSpeaking: boolean): HudMode {
  if (state === 'speaking' || isSpeaking) return 'speaking';
  if (state === 'thinking') return 'thinking';
  if (state === 'listening') return 'listening';
  if (state === 'connecting' || state === 'initializing') return 'connecting';
  return 'idle';
}

function easeAmp(mode: HudMode, rawAmplitude: number) {
  if (mode !== 'speaking') return mode === 'thinking' ? 0.18 : 0.06;
  return Math.min(1, Math.max(0.12, rawAmplitude * 1.9));
}

function rotatePoint(point: Point3, ax: number, ay: number, az: number): Point3 {
  const sinX = Math.sin(ax);
  const cosX = Math.cos(ax);
  const sinY = Math.sin(ay);
  const cosY = Math.cos(ay);
  const sinZ = Math.sin(az);
  const cosZ = Math.cos(az);

  let x = point.x;
  let y = point.y * cosX - point.z * sinX;
  let z = point.y * sinX + point.z * cosX;

  const x2 = x * cosY + z * sinY;
  z = -x * sinY + z * cosY;
  x = x2;

  const x3 = x * cosZ - y * sinZ;
  y = x * sinZ + y * cosZ;

  return { x: x3, y, z };
}

function projectPoint(point: Point3, cx: number, cy: number, radius: number): ProjectedPoint {
  const depth = 2.8 - point.z * 0.7;
  const scale = 1.18 / depth;

  return {
    x: cx + point.x * radius * scale,
    y: cy + point.y * radius * scale,
    z: point.z,
    scale,
  };
}

function drawSegmentedRing(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  radius: number,
  count: number,
  rotation: number,
  color: Rgb,
  options: {
    alpha: number;
    lineWidth: number;
    fillRatio: number;
    pulse?: number;
    alternate?: boolean;
  }
) {
  const step = (Math.PI * 2) / count;

  ctx.save();
  ctx.lineCap = 'butt';
  ctx.shadowColor = rgba(color, 0.8);
  ctx.shadowBlur = options.lineWidth * 2.6;

  for (let i = 0; i < count; i += 1) {
    const skip = options.alternate && i % 4 === 1;
    if (skip) continue;

    const wave = 1 + Math.sin(rotation * 2.5 + i * 0.9) * (options.pulse ?? 0);
    const alpha = options.alpha * wave;
    const start = rotation + i * step;
    const end = start + step * options.fillRatio;

    ctx.beginPath();
    ctx.arc(cx, cy, radius, start, end);
    ctx.strokeStyle = rgba(color, alpha);
    ctx.lineWidth = options.lineWidth;
    ctx.stroke();
  }

  ctx.restore();
}

function drawBackground(
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number,
  color: Rgb,
  amp: number
) {
  const cx = width / 2;
  const cy = height / 2;
  const maxR = Math.hypot(width, height) * 0.58;

  const base = ctx.createRadialGradient(cx, cy, 0, cx, cy, maxR);
  base.addColorStop(0, rgba(color, 0.22 + amp * 0.12));
  base.addColorStop(0.34, 'rgba(0, 64, 77, 0.18)');
  base.addColorStop(0.7, 'rgba(0, 20, 26, 0.92)');
  base.addColorStop(1, 'rgba(0, 4, 8, 1)');
  ctx.fillStyle = base;
  ctx.fillRect(0, 0, width, height);

  const vignette = ctx.createRadialGradient(cx, cy, Math.min(width, height) * 0.12, cx, cy, maxR);
  vignette.addColorStop(0, 'rgba(0, 0, 0, 0)');
  vignette.addColorStop(0.76, 'rgba(0, 0, 0, 0.08)');
  vignette.addColorStop(1, 'rgba(0, 0, 0, 0.88)');
  ctx.fillStyle = vignette;
  ctx.fillRect(0, 0, width, height);
}

function drawRadialRays(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  base: number,
  rotation: number,
  color: Rgb,
  amp: number
) {
  const count = 72;

  ctx.save();
  ctx.shadowColor = rgba(color, 0.45);
  ctx.shadowBlur = 8 + amp * 16;
  ctx.lineCap = 'round';

  for (let i = 0; i < count; i += 1) {
    const angle = rotation + (Math.PI * 2 * i) / count;
    const inner = base * (0.055 + (i % 3) * 0.006);
    const outer = base * (0.82 + Math.sin(rotation * 3 + i) * 0.02 + amp * 0.16);
    const alpha = 0.08 + (i % 6 === 0 ? 0.15 : 0) + amp * 0.08;

    ctx.beginPath();
    ctx.moveTo(cx + Math.cos(angle) * inner, cy + Math.sin(angle) * inner);
    ctx.lineTo(cx + Math.cos(angle) * outer, cy + Math.sin(angle) * outer);
    ctx.strokeStyle = rgba(color, alpha);
    ctx.lineWidth = i % 6 === 0 ? 2.1 : 1.2;
    ctx.stroke();
  }

  ctx.restore();
}

function drawAudioWaves(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  ringRadius: number,
  color: Rgb,
  waveA: number,
  amp: number,
  mode: HudMode
) {
  if (mode !== 'speaking' && mode !== 'thinking') return;

  const strength = mode === 'speaking' ? amp : 0.16;
  const waveCount = mode === 'speaking' ? 5 : 2;

  ctx.save();
  ctx.shadowColor = rgba(color, 0.8);
  ctx.shadowBlur = 18 + strength * 28;

  for (let i = 0; i < waveCount; i += 1) {
    const phase = (waveA + i / waveCount) % 1;
    const radius = ringRadius * (0.98 + phase * (0.44 + strength * 0.28));
    const alpha = (1 - phase) * (0.12 + strength * 0.38);

    ctx.beginPath();
    ctx.arc(cx, cy, radius, 0, Math.PI * 2);
    ctx.strokeStyle = rgba(color, alpha);
    ctx.lineWidth = 1.4 + strength * 3;
    ctx.stroke();
  }

  ctx.restore();
}

function drawPolyhedron(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  radius: number,
  state: HudState,
  color: Rgb,
  time: number,
  mode: HudMode
) {
  const pulse = mode === 'thinking' ? 0.09 : mode === 'speaking' ? 0.13 + state.amp * 0.2 : 0.025;
  const localRadius = radius * (1 + Math.sin(time * 2.2) * pulse);
  const pointDrift = mode === 'thinking' || mode === 'speaking' ? radius * (0.02 + state.amp * 0.035) : radius * 0.006;
  const ax = state.polyA * 0.72;
  const ay = state.polyA * (mode === 'speaking' ? 1.32 : 0.88);
  const az = state.polyA * 0.28;

  const points = ICOSA_POINTS.map((point, index) => {
    const drift = {
      x: Math.sin(time * 1.6 + index * 1.9) * pointDrift,
      y: Math.cos(time * 1.3 + index * 1.4) * pointDrift,
      z: Math.sin(time * 1.1 + index * 1.1) * 0.05,
    };
    const rotated = rotatePoint(
      {
        x: point.x + drift.x / Math.max(radius, 1),
        y: point.y + drift.y / Math.max(radius, 1),
        z: point.z + drift.z,
      },
      ax,
      ay,
      az
    );

    return projectPoint(rotated, cx, cy, localRadius * 2.45);
  });

  ctx.save();
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  ctx.shadowColor = rgba(color, 0.95);
  ctx.shadowBlur = 10 + state.amp * 24;

  for (const [from, to] of ICOSA_EDGES) {
    const a = points[from];
    const b = points[to];
    const depth = (a.z + b.z + 2) / 4;

    ctx.beginPath();
    ctx.moveTo(a.x, a.y);
    ctx.lineTo(b.x, b.y);
    ctx.strokeStyle = rgba(color, 0.42 + depth * 0.45 + state.amp * 0.18);
    ctx.lineWidth = 1.5 + depth * 2.2 + state.amp * 2.2;
    ctx.stroke();
  }

  points.forEach((point, index) => {
    const dot = 4.5 + point.scale * 9 + (index % 3 === 0 ? state.amp * 9 : state.amp * 4);
    const glow = 0.54 + point.scale * 0.42;

    ctx.beginPath();
    ctx.fillStyle = rgba(color, glow);
    ctx.arc(point.x, point.y, dot, 0, Math.PI * 2);
    ctx.fill();
  });

  ctx.restore();
}

function drawHud(
  ctx: CanvasRenderingContext2D,
  hud: HudState,
  width: number,
  height: number,
  time: number,
  props: Required<Pick<CentralOrbProps, 'isSpeaking' | 'audioAmplitude' | 'color'>> & {
    state?: AgentState;
  }
) {
  const color = parseColor(props.color);
  const mode = getMode(props.state, props.isSpeaking);
  const dt = hud.lastTime ? Math.min(0.05, Math.max(0.001, time - hud.lastTime)) : 0.016;
  hud.lastTime = time;

  const targetAmp = easeAmp(mode, props.audioAmplitude);
  hud.amp += (targetAmp - hud.amp) * (mode === 'speaking' ? 0.16 : 0.08);

  const speed = {
    connecting: 0.25,
    idle: 0.34,
    listening: 0.5,
    thinking: 1.15,
    speaking: 2.25,
  }[mode];

  hud.ringA += dt * speed * (0.22 + hud.amp * 0.55);
  hud.ringB -= dt * speed * (0.17 + hud.amp * 0.38);
  hud.ringC += dt * speed * (0.08 + hud.amp * 0.18);
  hud.polyA += dt * (mode === 'speaking' ? 1.65 : mode === 'thinking' ? 0.78 : 0.22);
  hud.waveA = (hud.waveA + dt * (mode === 'speaking' ? 0.85 + hud.amp * 0.95 : 0.24)) % 1;

  const cx = width / 2;
  const cy = height / 2;
  const base = Math.min(width, height);
  const ringRadius = base * (width > height * 1.2 ? 0.39 : 0.35);
  const opacityScale = mode === 'connecting' ? 0.72 : 1;

  ctx.clearRect(0, 0, width, height);
  drawBackground(ctx, width, height, color, hud.amp);
  drawRadialRays(ctx, cx, cy, base, hud.ringC, color, hud.amp);

  ctx.save();
  ctx.globalAlpha = opacityScale;

  drawAudioWaves(ctx, cx, cy, ringRadius, color, hud.waveA, hud.amp, mode);

  drawSegmentedRing(ctx, cx, cy, ringRadius * 1.56, 36, hud.ringA, color, {
    alpha: 0.46 + hud.amp * 0.22,
    fillRatio: 0.42,
    lineWidth: Math.max(8, base * 0.012),
    pulse: mode === 'speaking' ? 0.24 : 0.06,
    alternate: true,
  });
  drawSegmentedRing(ctx, cx, cy, ringRadius * 1.34, 42, hud.ringB, color, {
    alpha: 0.54 + hud.amp * 0.25,
    fillRatio: 0.34,
    lineWidth: Math.max(6, base * 0.009),
    pulse: mode === 'speaking' ? 0.18 : 0.04,
  });
  drawSegmentedRing(ctx, cx, cy, ringRadius * 1.13, 48, hud.ringA * -0.75, color, {
    alpha: 0.68 + hud.amp * 0.22,
    fillRatio: 0.26,
    lineWidth: Math.max(5, base * 0.007),
    pulse: mode === 'speaking' ? 0.2 : 0.05,
    alternate: true,
  });

  ctx.save();
  ctx.shadowColor = rgba(color, 0.85);
  ctx.shadowBlur = 22 + hud.amp * 30;
  ctx.beginPath();
  ctx.arc(cx, cy, ringRadius, 0, Math.PI * 2);
  ctx.strokeStyle = rgba(color, 0.58 + hud.amp * 0.2);
  ctx.lineWidth = Math.max(10, base * 0.013);
  ctx.stroke();
  ctx.restore();

  ctx.save();
  ctx.beginPath();
  ctx.arc(cx, cy, ringRadius * 0.86, 0, Math.PI * 2);
  ctx.strokeStyle = rgba(color, 0.1 + hud.amp * 0.08);
  ctx.lineWidth = 1.2;
  ctx.stroke();
  ctx.restore();

  drawPolyhedron(ctx, cx, cy, ringRadius * 0.52, hud, color, time, mode);

  ctx.save();
  const centerGlow = ctx.createRadialGradient(cx, cy, 0, cx, cy, ringRadius * 0.42);
  centerGlow.addColorStop(0, rgba(color, 0.28 + hud.amp * 0.28));
  centerGlow.addColorStop(0.26, rgba(color, 0.1 + hud.amp * 0.14));
  centerGlow.addColorStop(1, rgba(color, 0));
  ctx.fillStyle = centerGlow;
  ctx.fillRect(cx - ringRadius, cy - ringRadius, ringRadius * 2, ringRadius * 2);
  ctx.restore();

  ctx.restore();
}

export function CentralOrb({
  state,
  isSpeaking = false,
  audioAmplitude = 0,
  color = DEFAULT_COLOR,
  className,
}: CentralOrbProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const propsRef = useRef({ state, isSpeaking, audioAmplitude, color });
  const hudRef = useRef<HudState>({
    amp: 0,
    ringA: 0,
    ringB: 0,
    ringC: 0,
    polyA: 0,
    waveA: 0,
    lastTime: 0,
  });

  propsRef.current = { state, isSpeaking, audioAmplitude, color };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let active = true;
    let frame = 0;
    let width = 1;
    let height = 1;

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = Math.max(1, Math.floor(rect.width));
      height = Math.max(1, Math.floor(rect.height));
      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const observer = new ResizeObserver(resize);
    observer.observe(canvas);
    resize();

    const loop = (timeMs: number) => {
      if (!active) return;
      drawHud(ctx, hudRef.current, width, height, timeMs / 1000, propsRef.current);
      frame = requestAnimationFrame(loop);
    };

    frame = requestAnimationFrame(loop);

    return () => {
      active = false;
      cancelAnimationFrame(frame);
      observer.disconnect();
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      className={cn('pointer-events-none h-full w-full bg-transparent', className)}
      style={{ background: 'transparent' }}
    />
  );
}

export default CentralOrb;

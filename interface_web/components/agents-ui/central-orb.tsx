'use client';

import { useEffect, useRef } from 'react';
import { cn } from '@/lib/shadcn/utils';

interface CentralOrbProps {
  size?: number;
  isSpeaking?: boolean;
  audioAmplitude?: number;
  color?: string;
  className?: string;
}

interface Particle {
  angle: number;
  radius: number;
  size: number;
  speed: number;
  alpha: number;
}

interface OrbState {
  outerA: number;
  innerA: number;
  rayA: number;
  smoothedAmp: number;
  particles: Particle[];
  glyphCache: Map<string, HTMLCanvasElement>;
}

const OUTER_TEXT = '☽ ✦ ☿ ♄ ♃ ☉ ANTIGRAVITY AI ✦ JARVIS ✦ ';
const INNER_TEXT = '⊕ ⊗ ◈ ⊛ ◉ △ ◇ ✦ ';

function createParticles(count: number): Particle[] {
  return Array.from({ length: count }, (_, index) => ({
    angle: (Math.PI * 2 * index) / count,
    radius: 0.18 + Math.random() * 0.78,
    size: 0.8 + Math.random() * 2.2,
    speed: 0.0002 + Math.random() * 0.0008,
    alpha: 0.25 + Math.random() * 0.55,
  }));
}

function getGlyph(
  cache: Map<string, HTMLCanvasElement>,
  glyph: string,
  fontSize: number,
  color: string
) {
  const key = `${glyph}-${Math.round(fontSize)}-${color}`;
  const cached = cache.get(key);
  if (cached) return cached;

  const canvas = document.createElement('canvas');
  const padding = Math.ceil(fontSize * 0.8);
  canvas.width = Math.ceil(fontSize * 2.4 + padding * 2);
  canvas.height = Math.ceil(fontSize * 2.4 + padding * 2);
  const ctx = canvas.getContext('2d');
  if (!ctx) return canvas;

  ctx.font = `700 ${fontSize}px 'Segoe UI Symbol', 'Apple Symbols', 'Segoe UI', Arial, sans-serif`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.lineWidth = Math.max(2, fontSize * 0.12);
  ctx.strokeStyle = 'rgba(12, 5, 0, 0.92)';
  ctx.shadowColor = color;
  ctx.shadowBlur = fontSize * 0.65;
  ctx.strokeText(glyph, canvas.width / 2, canvas.height / 2);
  ctx.fillStyle = '#fffde0';
  ctx.fillText(glyph, canvas.width / 2, canvas.height / 2);
  cache.set(key, canvas);
  return canvas;
}

function drawTextRing(
  ctx: CanvasRenderingContext2D,
  state: OrbState,
  text: string,
  cx: number,
  cy: number,
  radius: number,
  fontSize: number,
  rotation: number,
  color: string,
  clockwise: boolean
) {
  const chars = text.repeat(4).split('');
  const step = (Math.PI * 2) / chars.length;

  chars.forEach((char, index) => {
    if (char === ' ') return;
    const angle = rotation + step * index * (clockwise ? 1 : -1);
    const glyph = getGlyph(state.glyphCache, char, fontSize, color);
    ctx.save();
    ctx.translate(cx + Math.cos(angle) * radius, cy + Math.sin(angle) * radius);
    ctx.rotate(angle + Math.PI / 2);
    ctx.drawImage(glyph, -glyph.width / 2, -glyph.height / 2);
    ctx.restore();
  });
}

function drawFlames(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  r: number,
  t: number,
  amp: number
) {
  const rays = 32;
  for (let i = 0; i < rays; i += 1) {
    const angle = (Math.PI * 2 * i) / rays + t * 0.0003;
    const length = r * (0.2 + (i % 2 ? 0.22 : 0.36) + amp * 0.18);
    const points = 18;
    ctx.beginPath();
    for (let p = 0; p <= points; p += 1) {
      const f = p / points;
      const waveEnv = Math.sin(f * Math.PI);
      const wobble = Math.sin(t * 0.006 + i * 0.9 + f * 8) * r * 0.018 * waveEnv * (1 + amp);
      const rr = r * 0.08 + f * length;
      const x = cx + Math.cos(angle) * rr + Math.cos(angle + Math.PI / 2) * wobble;
      const y = cy + Math.sin(angle) * rr + Math.sin(angle + Math.PI / 2) * wobble;
      if (p === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.strokeStyle = i % 2 ? 'rgba(255, 178, 0, 0.42)' : 'rgba(255, 245, 190, 0.72)';
    ctx.lineWidth = i % 2 ? 1.0 : 1.8;
    ctx.shadowColor = '#ff9d00';
    ctx.shadowBlur = 12 + amp * 22;
    ctx.stroke();
  }
  ctx.shadowBlur = 0;
}

function drawOrb(
  ctx: CanvasRenderingContext2D,
  state: OrbState,
  width: number,
  height: number,
  t: number,
  isSpeaking: boolean,
  amplitude: number,
  color: string
) {
  const cx = width / 2;
  const cy = height / 2;
  const r = Math.min(width, height) * 0.499;
  const ampTarget = isSpeaking ? Math.min(1, amplitude * 1.35) : 0;
  state.smoothedAmp += (ampTarget - state.smoothedAmp) * 0.08;
  const amp = state.smoothedAmp;
  const breath = 1 + Math.sin(t * 0.003) * 0.025 + amp * 0.22;

  ctx.clearRect(0, 0, width, height);
  ctx.save();
  ctx.translate(cx, cy);
  ctx.scale(breath, breath);
  ctx.translate(-cx, -cy);

  const atmosphere = ctx.createRadialGradient(cx, cy, 0, cx, cy, r);
  atmosphere.addColorStop(0, 'rgba(255, 210, 60, 0.22)');
  atmosphere.addColorStop(0.5, 'rgba(255, 140, 0, 0.07)');
  atmosphere.addColorStop(1, 'rgba(0, 0, 0, 0)');
  ctx.fillStyle = atmosphere;
  ctx.fillRect(0, 0, width, height);

  state.particles.forEach((particle) => {
    particle.angle += particle.speed * (1 + amp * 2);
    const px = cx + Math.cos(particle.angle) * r * particle.radius;
    const py = cy + Math.sin(particle.angle) * r * particle.radius;
    ctx.beginPath();
    ctx.fillStyle = `rgba(255, 202, 45, ${particle.alpha})`;
    ctx.shadowColor = '#ffd700';
    ctx.shadowBlur = 8;
    ctx.arc(px, py, particle.size, 0, Math.PI * 2);
    ctx.fill();
  });
  ctx.shadowBlur = 0;

  drawFlames(ctx, cx, cy, r, t, amp);

  const sides = 12;
  const polygonR = r * 0.46;
  const fill = ctx.createRadialGradient(cx, cy, 0, cx, cy, polygonR);
  fill.addColorStop(0, 'rgba(255, 253, 232, 0.56)');
  fill.addColorStop(0.28, 'rgba(255, 215, 0, 0.38)');
  fill.addColorStop(0.72, 'rgba(255, 140, 0, 0.18)');
  fill.addColorStop(1, 'rgba(140, 60, 0, 0.02)');
  ctx.beginPath();
  for (let i = 0; i <= sides; i += 1) {
    const angle = -Math.PI / 2 + (Math.PI * 2 * i) / sides + state.rayA;
    const x = cx + Math.cos(angle) * polygonR;
    const y = cy + Math.sin(angle) * polygonR;
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.fillStyle = fill;
  ctx.fill();
  ctx.strokeStyle = 'rgba(255, 210, 60, 0.82)';
  ctx.lineWidth = 4;
  ctx.shadowColor = '#ffb000';
  ctx.shadowBlur = 30 + amp * 35;
  ctx.stroke();
  ctx.shadowBlur = 0;

  for (let ring = 0; ring < 5; ring += 1) {
    ctx.beginPath();
    ctx.arc(cx, cy, r * (0.2 + ring * 0.11), 0, Math.PI * 2);
    ctx.strokeStyle = `rgba(255, 190, 25, ${0.16 - ring * 0.018})`;
    ctx.lineWidth = 1;
    ctx.stroke();
  }

  for (let i = 0; i < 120; i += 1) {
    const angle = (Math.PI * 2 * i) / 120 + state.outerA;
    const major = i % 10 === 0;
    const inner = r * (major ? 0.82 : 0.86);
    const outer = r * 0.91;
    ctx.beginPath();
    ctx.moveTo(cx + Math.cos(angle) * inner, cy + Math.sin(angle) * inner);
    ctx.lineTo(cx + Math.cos(angle) * outer, cy + Math.sin(angle) * outer);
    ctx.strokeStyle = major ? 'rgba(255, 245, 180, 0.75)' : 'rgba(255, 176, 0, 0.32)';
    ctx.lineWidth = major ? 1.6 : 0.7;
    ctx.stroke();
  }

  drawTextRing(ctx, state, OUTER_TEXT, cx, cy, r * 0.78, Math.max(16, r * 0.075), state.outerA, color, false);
  drawTextRing(ctx, state, INNER_TEXT, cx, cy, r * 0.58, Math.max(13, r * 0.055), state.innerA, '#ffd000', true);

  if (amp > 0.02) {
    for (let i = 0; i < 5; i += 1) {
      const phase = (t * 0.002 + i / 5) % 1;
      ctx.beginPath();
      ctx.arc(cx, cy, r * (0.12 + phase * 0.82), 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(255, ${220 - i * 24}, 80, ${(1 - phase) * amp * 0.32})`;
      ctx.lineWidth = 2;
      ctx.stroke();
    }
  }

  const coreR = r * (0.1 + amp * 0.035);
  const core = ctx.createRadialGradient(cx - coreR * 0.25, cy - coreR * 0.25, 0, cx, cy, coreR * 2.2);
  core.addColorStop(0, '#ffffff');
  core.addColorStop(0.22, '#fffde8');
  core.addColorStop(0.52, '#ffd700');
  core.addColorStop(1, '#c96f00');
  ctx.beginPath();
  ctx.shadowColor = '#ffd700';
  ctx.shadowBlur = 60 + amp * 90;
  ctx.fillStyle = core;
  ctx.arc(cx, cy, coreR, 0, Math.PI * 2);
  ctx.fill();
  ctx.shadowBlur = 0;
  ctx.beginPath();
  ctx.fillStyle = 'rgba(255, 255, 255, 0.72)';
  ctx.arc(cx - coreR * 0.28, cy - coreR * 0.32, coreR * 0.23, 0, Math.PI * 2);
  ctx.fill();

  ctx.restore();

  state.outerA -= 0.00085 * (1 + amp * 2);
  state.innerA += 0.0013 * (1 + amp * 2);
  state.rayA += 0.0003 * (1 + amp * 2);
}

export function CentralOrb({
  size = 620,
  isSpeaking = false,
  audioAmplitude = 0,
  color = '#ffb200',
  className,
}: CentralOrbProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const propsRef = useRef({ isSpeaking, audioAmplitude, color });
  const stateRef = useRef<OrbState>({
    outerA: 0,
    innerA: 0,
    rayA: 0,
    smoothedAmp: 0,
    particles: createParticles(145),
    glyphCache: new Map(),
  });

  propsRef.current = { isSpeaking, audioAmplitude, color };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let frame = 0;
    let active = true;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = size * dpr;
    canvas.height = size * dpr;
    canvas.style.width = `${size}px`;
    canvas.style.height = `${size}px`;
    ctx.scale(dpr, dpr);

    const loop = (time: number) => {
      if (!active) return;
      const { isSpeaking: speaking, audioAmplitude: amp, color: liveColor } = propsRef.current;
      drawOrb(ctx, stateRef.current, size, size, time, speaking, amp, liveColor);
      frame = requestAnimationFrame(loop);
    };

    frame = requestAnimationFrame(loop);
    return () => {
      active = false;
      cancelAnimationFrame(frame);
    };
  }, [size]);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      className={cn('pointer-events-none bg-transparent', className)}
      style={{ background: 'transparent' }}
    />
  );
}

export default CentralOrb;


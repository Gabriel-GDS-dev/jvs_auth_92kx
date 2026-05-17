'use client';

import React, { useEffect, useRef } from 'react';

type VantaEffect = {
  destroy: () => void;
};

type VantaFactory = (options: {
  el: HTMLDivElement;
  p5: unknown;
  mouseControls: boolean;
  touchControls: boolean;
  gyroControls: boolean;
  minHeight: number;
  minWidth: number;
  scale: number;
  scaleMobile: number;
  color: number;
  backgroundColor: number;
  spacing: number;
  chaos: number;
}) => VantaEffect;

type VantaWindow = Window & {
  VANTA?: {
    TRUNK?: VantaFactory;
  };
  p5?: unknown;
};

interface VantaOrbProps {
  isConnected: boolean;
  color: number;
  vantaRef: React.MutableRefObject<VantaEffect | null>;
}

export const VantaOrb = ({ isConnected, color, vantaRef }: VantaOrbProps) => {
  const localRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let vantaEffect: VantaEffect | null = null;
    let attempts = 0;
    let initTimer: ReturnType<typeof setTimeout> | undefined;

    const tryInitVanta = () => {
      const el = localRef.current;
      const win = window as VantaWindow;
      const hasVanta = !!win.VANTA?.TRUNK;
      const hasP5 = !!win.p5;

      if (el && hasVanta && hasP5) {
        try {
          vantaEffect = win.VANTA!.TRUNK!({
            el,
            p5: win.p5,
            mouseControls: false,
            touchControls: false,
            gyroControls: false,
            minHeight: 200.0,
            minWidth: 200.0,
            scale: 1.0,
            scaleMobile: 1.0,
            color: color,
            backgroundColor: 0x000000,
            spacing: 0.0,
            chaos: 3.0,
          });
          vantaRef.current = vantaEffect;
        } catch (e) {
          console.error('Vanta Orb Init Error:', e);
          attempts++;
          if (attempts < 10) initTimer = setTimeout(tryInitVanta, 500);
        }
      } else {
        attempts++;
        if (attempts < 50) initTimer = setTimeout(tryInitVanta, 100);
      }
    };

    tryInitVanta();

    return () => {
      clearTimeout(initTimer);
      if (vantaEffect) {
        try {
          if (vantaRef.current === vantaEffect) {
            vantaRef.current = null;
          }
          vantaEffect.destroy();
        } catch (error) {
          console.error('Vanta Orb Cleanup Error:', error);
        }
      }
    };
  }, [isConnected, color, vantaRef]);

  return (
    <div
      ref={localRef}
      className="h-[1000px] w-[1000px]"
      style={{
        transform: 'scale(0.5) translateY(-15%)',
        transformOrigin: 'center center',
      }}
    />
  );
};

export default VantaOrb;

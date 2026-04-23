'use client';

import React, { useEffect, useRef } from 'react';

interface VantaOrbProps {
  isConnected: boolean;
  color: number;
  vantaRef: React.MutableRefObject<any>;
}

export const VantaOrb = ({ isConnected, color, vantaRef }: VantaOrbProps) => {
  const localRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let vantaEffect: any = null;
    let attempts = 0;
    let initTimer: NodeJS.Timeout;

    const tryInitVanta = () => {
      const el = localRef.current;
      const win = window as any;
      const hasVanta = !!win.VANTA?.TRUNK;
      const hasP5 = !!win.p5;

      if (el && hasVanta && hasP5) {
        try {
          vantaEffect = win.VANTA.TRUNK({
            el: el,
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
        } catch (e) { }
      }
    };
  }, [isConnected, color, vantaRef]);

  return (
    <div
      ref={localRef}
      className="w-[1000px] h-[1000px]"
      style={{
        transform: 'scale(0.5) translateY(-15%)',
        transformOrigin: 'center center',
      }}
    />
  );
};

export default VantaOrb;

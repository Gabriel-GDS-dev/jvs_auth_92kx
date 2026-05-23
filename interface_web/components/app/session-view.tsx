'use client';

import React, { useEffect, useRef, useState, memo } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import {
  useSessionContext,
  useSessionMessages,
  useVoiceAssistant,
  useRemoteParticipants,
} from '@livekit/components-react';
import type { AppConfig } from '@/app-config';
import {
  AgentControlBar,
  type AgentControlBarControls,
} from '@/components/agents-ui/agent-control-bar';
import { TileLayout } from '@/components/app/tile-layout';
import { cn } from '@/lib/shadcn/utils';

const MotionBottom = motion.create('div');

const BOTTOM_VIEW_MOTION_PROPS = {
  variants: {
    visible: {
      opacity: 1,
      translateY: '0%',
    },
    hidden: {
      opacity: 0,
      translateY: '100%',
    },
  },
  initial: 'hidden',
  animate: 'visible',
  exit: 'hidden',
  transition: {
    duration: 0.3,
    delay: 0.5,
    ease: 'easeOut' as const,
  },
};

interface FadeProps {
  top?: boolean;
  bottom?: boolean;
  className?: string;
}

export const Fade = memo(({ top = false, bottom = false, className }: FadeProps) => {
  return (
    <div
      className={cn(
        'from-background pointer-events-none h-4 bg-linear-to-b to-transparent',
        top && 'bg-linear-to-b',
        bottom && 'bg-linear-to-t',
        className
      )}
    />
  );
});

Fade.displayName = 'Fade';

interface SessionViewProps {
  appConfig: AppConfig;
  onManualDisconnect?: () => void;
}

import { AudioVisualizer } from '@/components/app/audio-visualizer';

export const SessionView = ({
  appConfig,
  onManualDisconnect,
  ...props
}: React.ComponentProps<'section'> & SessionViewProps) => {
  const session = useSessionContext();
  const { messages } = useSessionMessages(session);
  const { state: agentState } = useVoiceAssistant();
  const [chatOpen, setChatOpen] = useState(false);
  const scrollAreaRef = useRef<HTMLDivElement>(null);

  // Monitora participantes para detectar Persona (Alice/Járvis)
  const participants = useRemoteParticipants();
  const agentParticipant = participants.find(p => !p.isLocal);
  const agentPersona = agentParticipant?.attributes?.["agent_persona"] || "jarvis";

  const controls: AgentControlBarControls = {
    leave: true,
    microphone: true,
    chat: appConfig.supportsChatInput,
    camera: appConfig.supportsVideoInput,
    screenShare: appConfig.supportsScreenShare,
  };

  useEffect(() => {
    if (scrollAreaRef.current) {
      scrollAreaRef.current.scrollTop = scrollAreaRef.current.scrollHeight;
    }
  }, [messages, agentState]);

  const handleDisconnect = () => {
    if (onManualDisconnect) onManualDisconnect();
    try {
      if (session.end) session.end();
    } catch (e) {
      console.warn("Erro ao desconectar sessão:", e);
    }
  };

  // Definição de Cores Reativas
  const PERSONA_COLORS = {
    alice: '#ff69b4',
    jarvis: appConfig.audioVisualizerColor || '#00d8e6'
  };
  const currentColor = PERSONA_COLORS[agentPersona as keyof typeof PERSONA_COLORS] || PERSONA_COLORS.jarvis;

  return (
    <section
      className="relative flex h-svh w-svw flex-col overflow-hidden bg-[#000b0f]"
      {...props}
    >
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
        <div className="absolute inset-0 flex items-center justify-center overflow-hidden">
          <AnimatePresence mode="wait">
            <motion.div
              key={session.isConnected ? `rafael-${agentPersona}` : 'rafael-disconnected'}
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 1.2 }}
              transition={{ duration: 1.0, ease: "easeOut" }}
              className="absolute inset-0 flex items-center justify-center"
            >
              <AudioVisualizer 
                appConfig={{...appConfig, audioVisualizerColor: currentColor}} 
                isChatOpen={chatOpen}
                className="opacity-100"
              />
            </motion.div>
          </AnimatePresence>
        </div>

        <div className="relative z-10 w-full h-full">
          <TileLayout chatOpen={chatOpen} />
        </div>

        {/* Chat Overlay (Top Right, Transparent, Fade Out at Top) */}
        <div 
          ref={scrollAreaRef}
          className="pointer-events-none absolute top-6 right-5 z-30 flex max-h-[44vh] w-72 flex-col gap-3 overflow-y-auto opacity-75 mix-blend-screen scrollbar-hide md:top-8 md:right-8 md:w-80"
          style={{
            maskImage: 'linear-gradient(to bottom, transparent 0%, black 20%, black 100%)',
            WebkitMaskImage: 'linear-gradient(to bottom, transparent 0%, black 20%, black 100%)',
            scrollbarWidth: 'none'
          }}
        >
          <div className="flex flex-col gap-4 min-h-full justify-end pb-4 pt-12">
            <AnimatePresence>
              {messages.map((msg, index) => {
                const isLocal = msg.from?.isLocal;
                const messageId = typeof msg.id === 'string' ? msg.id.trim() : msg.id;
                const timestamp =
                  typeof msg.timestamp === 'number' || typeof msg.timestamp === 'string'
                    ? msg.timestamp
                    : '';
                const messageKey = [
                  messageId || `message-${index}`,
                  msg.from?.identity || (isLocal ? 'local' : 'remote'),
                  timestamp || index,
                  index,
                ].join('-');

                return (
                  <motion.div 
                    key={messageKey}
                    initial={{ opacity: 0, x: 20 }}
                    animate={{ opacity: 1, x: 0 }}
                    className={cn(
                      "max-w-[95%] break-words px-3 py-1 text-sm font-medium md:text-base",
                      isLocal ? "self-end text-right" : "self-start text-left"
                    )}
                    style={{
                      color: currentColor,
                      textShadow: `0 0 10px ${currentColor}80`,
                      borderLeft: !isLocal ? `2px solid ${currentColor}` : 'none',
                      borderRight: isLocal ? `2px solid ${currentColor}` : 'none',
                    }}
                  >
                    <span className="opacity-60 text-xs block mb-1 uppercase tracking-widest font-mono">
                      {isLocal ? 'Você' : agentPersona}
                    </span>
                    {msg.message}
                  </motion.div>
                );
              })}
              
              {messages.length === 0 && appConfig.isPreConnectBufferEnabled && (
                <motion.div
                  key="preconnect-buffer"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="self-end text-right py-1 px-3 text-sm font-medium opacity-60 italic"
                  style={{ color: currentColor, textShadow: `0 0 10px ${currentColor}80` }}
                >
                  <span className="block mb-1 uppercase tracking-widest font-mono text-[10px]">
                    Sistema
                  </span>
                  O Jarvis está ouvindo, pode falar...
                </motion.div>
              )}

              {/* Thinking Indicator */}
              {agentState === 'thinking' && (
                <motion.div
                  key="thinking-indicator"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="self-start text-left py-1 px-3 text-sm font-medium font-mono"
                  style={{ 
                    color: currentColor, 
                    textShadow: `0 0 10px ${currentColor}80`,
                    borderLeft: `2px solid ${currentColor}`
                  }}
                >
                  <span className="animate-pulse opacity-80">Processando...</span>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>

      <div className="flex-1 pointer-events-none" />

      <MotionBottom
        {...BOTTOM_VIEW_MOTION_PROPS}
        className="relative z-10 mx-auto mb-4 w-full max-w-3xl px-3"
      >
        <div className="pointer-events-auto relative mx-auto max-w-2xl bg-transparent pb-3 opacity-85 transition-opacity hover:opacity-100 md:pb-12">
          <AgentControlBar
            variant="livekit"
            controls={controls}
            isChatOpen={chatOpen}
            isConnected={true}
            onDisconnect={handleDisconnect}
            onIsChatOpenChange={setChatOpen}
          />
        </div>
      </MotionBottom>
    </section>
  );
};

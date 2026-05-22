import { Button } from '@/components/ui/button';

function WelcomeImage() {
  return (
    <svg
      width="64"
      height="64"
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className="mb-5 size-16 text-[#00d8e6] drop-shadow-[0_0_22px_rgba(0,216,230,0.7)]"
    >
      <path
        d="M15 24V40C15 40.7957 14.6839 41.5587 14.1213 42.1213C13.5587 42.6839 12.7956 43 12 43C11.2044 43 10.4413 42.6839 9.87868 42.1213C9.31607 41.5587 9 40.7957 9 40V24C9 23.2044 9.31607 22.4413 9.87868 21.8787C10.4413 21.3161 11.2044 21 12 21C12.7956 21 13.5587 21.3161 14.1213 21.8787C14.6839 22.4413 15 23.2044 15 24ZM22 5C21.2044 5 20.4413 5.31607 19.8787 5.87868C19.3161 6.44129 19 7.20435 19 8V56C19 56.7957 19.3161 57.5587 19.8787 58.1213C20.4413 58.6839 21.2044 59 22 59C22.7956 59 23.5587 58.6839 24.1213 58.1213C24.6839 57.5587 25 56.7957 25 56V8C25 7.20435 24.6839 6.44129 24.1213 5.87868C23.5587 5.31607 22.7956 5 22 5ZM32 13C31.2044 13 30.4413 13.3161 29.8787 13.8787C29.3161 14.4413 29 15.2044 29 16V48C29 48.7957 29.3161 49.5587 29.8787 50.1213C30.4413 50.6839 31.2044 51 32 51C32.7956 51 33.5587 50.6839 34.1213 50.1213C34.6839 49.5587 35 48.7957 35 48V16C35 15.2044 34.6839 14.4413 34.1213 13.8787C33.5587 13.3161 32.7956 13 32 13ZM42 21C41.2043 21 40.4413 21.3161 39.8787 21.8787C39.3161 22.4413 39 23.2044 39 24V40C39 40.7957 39.3161 41.5587 39.8787 42.1213C40.4413 42.6839 41.2043 43 42 43C42.7957 43 43.5587 42.6839 44.1213 42.1213C44.6839 41.5587 45 40.7957 45 40V24C45 23.2044 44.6839 22.4413 44.1213 21.8787C43.5587 21.3161 42.7957 21 42 21ZM52 17C51.2043 17 50.4413 17.3161 49.8787 17.8787C49.3161 18.4413 49 19.2044 49 20V44C49 44.7957 49.3161 45.5587 49.8787 46.1213C50.4413 46.6839 51.2043 47 52 47C52.7957 47 53.5587 46.6839 54.1213 46.1213C54.6839 45.5587 55 44.7957 55 44V20C55 19.2044 54.6839 18.4413 54.1213 17.8787C53.5587 17.3161 52.7957 17 52 17Z"
        fill="currentColor"
      />
    </svg>
  );
}

interface WelcomeViewProps {
  startButtonText: string;
  onStartCall: () => void;
}

export const WelcomeView = ({
  startButtonText,
  onStartCall,
  ref,
}: React.ComponentProps<'div'> & WelcomeViewProps) => {
  return (
    <div ref={ref} className="relative h-svh w-svw overflow-hidden bg-[#000b0f] text-[#d9feff]">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(0,216,230,0.16),rgba(0,20,26,0.22)_28%,rgba(0,0,0,0.94)_68%)]" />
      <div className="pointer-events-none absolute inset-x-0 top-1/2 mx-auto h-[44rem] w-[44rem] -translate-y-1/2 rounded-full border border-[#00d8e6]/20 shadow-[0_0_120px_rgba(0,216,230,0.14)]" />
      <div className="pointer-events-none absolute inset-x-0 top-1/2 mx-auto h-[30rem] w-[30rem] -translate-y-1/2 rounded-full border border-dashed border-[#00d8e6]/25" />

      <section className="relative z-10 flex h-svh flex-col items-center justify-center px-6 text-center">
        <WelcomeImage />

        <p className="max-w-prose pt-1 font-mono text-xs font-semibold tracking-[0.32em] text-[#00d8e6]/80 uppercase">
          Jarvis
        </p>
        <p className="mt-3 max-w-prose text-lg leading-7 font-medium text-[#d9feff]">
          Assistente de voz online
        </p>

        <Button
          size="lg"
          onClick={onStartCall}
          className="mt-8 h-12 w-72 rounded-full border border-[#00d8e6]/55 bg-[#00d8e6]/12 font-mono text-xs font-bold tracking-wider text-[#d9feff] uppercase shadow-[0_0_34px_rgba(0,216,230,0.22)] transition hover:bg-[#00d8e6]/22 hover:shadow-[0_0_44px_rgba(0,216,230,0.32)]"
        >
          {startButtonText}
        </Button>
      </section>

      <div className="fixed bottom-5 left-0 z-10 flex w-full items-center justify-center px-6">
        <p className="max-w-prose pt-1 text-center text-xs leading-5 font-normal text-[#7ddce4]/55 text-pretty md:text-sm">
          Configuracao e docs:{' '}
          <a
            target="_blank"
            rel="noopener noreferrer"
            href="https://docs.livekit.io/agents/start/voice-ai/"
            className="text-[#00d8e6]/80 underline underline-offset-4"
          >
            Voice AI quickstart
          </a>
          .
        </p>
      </div>
    </div>
  );
};

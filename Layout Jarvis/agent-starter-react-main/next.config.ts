import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  experimental: {
    optimizePackageImports: [
      '@phosphor-icons/react',
      'lucide-react',
      '@radix-ui/react-icons',
      'motion/react',
    ],
  },
  // Desabilitar source maps em produção para economizar memória se necessário
  productionBrowserSourceMaps: false,
};

export default nextConfig;

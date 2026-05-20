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
  webpack: (config, { dev }) => {
    if (dev) {
      // OneDrive can interfere with webpack's on-disk cache writes.
      config.cache = false;
    }

    return config;
  },
};

export default nextConfig;

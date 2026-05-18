import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  output: 'standalone',
  experimental: {
    // better-sqlite3 operuje natywnie w warstwie Node.js, Next musi to wiedzieć
    serverComponentsExternalPackages: ['better-sqlite3'],
  },
};

export default nextConfig;
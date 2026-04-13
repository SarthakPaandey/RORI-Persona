/** @type {import('next').NextConfig} */
// Where Next.js proxies /api/* and /health in dev and prod (FastAPI). Override with BACKEND_URL on Vercel.
const configuredBackendUrl =
  process.env.BACKEND_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  'http://127.0.0.1:8000';

function normalizeBackendUrl(url) {
  const trimmed = (url || '').trim();
  if (!trimmed) return 'http://127.0.0.1:8000';

  const withProtocol = /^https?:\/\//i.test(trimmed)
    ? trimmed
    : `https://${trimmed}`;

  return withProtocol.replace(/\/+$/, '');
}

const backendUrl = normalizeBackendUrl(configuredBackendUrl);

const nextConfig = {
  output: 'standalone',
  env: {
    // Leave empty to use same-origin + rewrites (recommended). Set only to force direct API URL in the browser.
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL ?? '',
  },
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${backendUrl}/api/:path*`,
      },
      {
        source: '/health',
        destination: `${backendUrl}/health`,
      },
    ];
  },
};

module.exports = nextConfig;

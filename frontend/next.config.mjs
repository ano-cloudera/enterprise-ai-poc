const apiTarget = process.env.BACKEND_API_URL || 'http://127.0.0.1:8000'

/** @type {import('next').NextConfig} */
const nextConfig = {
  outputFileTracingRoot: process.cwd(),
  async rewrites() {
    return [{ source: '/api/:path*', destination: `${apiTarget}/api/:path*` }]
  },
}

export default nextConfig

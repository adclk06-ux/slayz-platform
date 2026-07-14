const path = require("path");

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  turbopack: process.env.NODE_ENV === "development" ? { root: path.join(__dirname) } : undefined,
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  async rewrites() {
    // REST is intentionally proxied through Next.js. This keeps the httpOnly
    // refresh cookie first-party in both local and production deployments.
    const backend = (process.env.BACKEND_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
    return [
      { source: "/api/:path*", destination: `${backend}/api/:path*` },
      // Useful on hosts that support WebSocket proxying. On Vercel, set
      // NEXT_PUBLIC_WS_URL to the backend URL for a direct authenticated socket.
      { source: "/socket.io/:path*", destination: `${backend}/socket.io/:path*` },
    ];
  },
};

module.exports = nextConfig;

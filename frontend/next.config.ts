import type { NextConfig } from "next";

/**
 * The browser only ever talks to its own origin. Requests to `/api/*` are
 * proxied to the Django backend, so the HttpOnly auth cookies stay first-party
 * and no CORS pre-flight is involved in development.
 */
const backendOrigin = process.env.BACKEND_ORIGIN ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // Django's API routes are slash-terminated. Without this, Next redirects
  // `/api/auth/login/` to its slashless form before the rewrite is applied;
  // Django redirects it straight back, and the browser eventually reports a
  // failed network request instead of completing login.
  skipTrailingSlashRedirect: true,
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${backendOrigin}/api/:path*/` },
      { source: "/media/:path*", destination: `${backendOrigin}/media/:path*` },
    ];
  },
};

export default nextConfig;

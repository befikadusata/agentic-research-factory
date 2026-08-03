import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // `standalone` exists for the Docker image, whose runner stage copies
  // `.next/standalone` and runs its `server.js`. Vercel builds through its own
  // output pipeline and never reads that directory, so the mode is dead weight
  // there — `VERCEL` is set automatically during a Vercel build, so the two
  // targets each get the output they actually consume without a second config.
  output: process.env.VERCEL ? undefined : "standalone",
};

export default nextConfig;

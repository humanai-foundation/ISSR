import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Multi-stage Docker build (web/Dockerfile) copies .next/standalone, which
  // only exists with this set -- without it the image ships full
  // node_modules instead of the pruned trace.
  output: "standalone",
  async redirects() {
    return [{ source: "/", destination: "/opportunities", permanent: false }];
  },
};

export default nextConfig;

/** @type {import('next').NextConfig} */
const defaultApiUrl =
  process.env.NEXT_PUBLIC_API_URL || "https://api.run.ingarena.net";

const nextConfig = {
  reactStrictMode: true,
  env: {
    NEXT_PUBLIC_API_URL: defaultApiUrl,
  },
  async headers() {
    const noStoreHeaders = [
      { key: "Cache-Control", value: "no-store, no-cache, must-revalidate, proxy-revalidate, max-age=0" },
      { key: "Pragma", value: "no-cache" },
      { key: "Expires", value: "0" },
      { key: "Surrogate-Control", value: "no-store" },
    ];
    return [
      { source: "/", headers: noStoreHeaders },
      { source: "/jobs", headers: noStoreHeaders },
      { source: "/jobs/:path*", headers: noStoreHeaders },
    ];
  },
};

export default nextConfig;

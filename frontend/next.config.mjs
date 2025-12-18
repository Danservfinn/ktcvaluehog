/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "export", // Static export for Cloudflare Pages
  images: {
    unoptimized: true, // Required for static export
  },
  // Environment variables available client-side
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || "https://dynasty-api-production.up.railway.app",
  },
};

export default nextConfig;

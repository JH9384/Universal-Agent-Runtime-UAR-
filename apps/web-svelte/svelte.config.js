import adapter from '@sveltejs/adapter-vercel';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
  preprocess: vitePreprocess(),
  kit: {
    adapter: adapter({
      runtime: 'nodejs20.x',
    }),
    alias: {
      $lib: './src/lib',
      $services: './src/lib/services',
      $components: './src/lib/components',
    },
  },
};

export default config;

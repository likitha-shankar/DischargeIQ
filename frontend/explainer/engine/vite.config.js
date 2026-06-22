/**
 * File: frontend/explainer/engine/vite.config.js
 * Component: Anatomy Explainer — Build Config
 * Description: Vite build config for the self-contained anatomy explainer bundle.
 *
 * Key choices:
 *   - base: './'   → relative asset paths so Flutter WebView can load the
 *                    dist/ folder from local file:// or bundled app assets.
 *   - assetsInlineLimit: 0 → never inline GLBs into the JS bundle (they can
 *                           be 10–50 MB; streaming load is correct).
 *   - Single HTML entry with all JS tree-shaken and bundled by Rollup.
 *   - Draco decoder files live in public/draco/ (copied there by the asset
 *     pipeline script); Vite copies public/ to dist/ verbatim.
 */

import { defineConfig } from 'vite';

export default defineConfig({
  base: './',
  build: {
    outDir: 'dist',
    assetsInlineLimit: 0,
    rollupOptions: {
      input: 'index.html',
      output: {
        // Stable chunk names so Flutter asset manifests do not break on rebuild.
        entryFileNames: 'assets/[name].js',
        chunkFileNames: 'assets/[name]-[hash].js',
        assetFileNames: 'assets/[name]-[hash][extname]',
      },
    },
  },
  // Allow three.js addons to be resolved without full path.
  resolve: {
    alias: {
      'three/addons': 'three/examples/jsm',
    },
  },
});

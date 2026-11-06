import { defineConfig } from 'astro/config';

const configuredBase = process.env.PUBLIC_BASE;
const base = configuredBase === undefined
  ? '/youtuber'
  : configuredBase === '/'
    ? ''
    : configuredBase;

export default defineConfig({
  site: 'https://ganghuxie.github.io',
  base,
  output: 'static',
  build: { format: 'directory' },
  trailingSlash: 'always',
});

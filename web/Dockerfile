# The Nitro output holds no native code, so one build on the builder's own platform
# serves every target platform. Both build stages are pinned to that platform.
FROM --platform=$BUILDPLATFORM oven/bun:1.3.14 AS bun

# Build stage: bun installs the dependencies from the lockfile, Node runs the Nuxt build.
FROM --platform=$BUILDPLATFORM node:22-slim AS build
COPY --from=bun /usr/local/bin/bun /usr/local/bin/bun
WORKDIR /app
COPY package.json bun.lock ./
# The postinstall script prepares Nuxt types and needs the sources; the build does it anyway.
RUN bun install --frozen-lockfile --ignore-scripts
COPY . .
RUN bun run build

# Runtime stage: the self-contained Nitro output on Node. Settings come from the
# environment when the container starts (server/utils/settings.ts).
FROM node:22-slim
ENV NODE_ENV=production
WORKDIR /app
COPY --from=build /app/.output ./.output
USER node
EXPOSE 3000
CMD ["node", ".output/server/index.mjs"]

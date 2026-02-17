# Stage 1: Builder
FROM registry.access.redhat.com/ubi9/nodejs-22 AS builder

USER 0
RUN npm install -g pnpm@10
USER 1001

WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY . .
RUN pnpm build

# Stage 2: Runtime
FROM registry.access.redhat.com/ubi9/nodejs-22-minimal

USER 1001
WORKDIR /app
COPY --from=builder --chown=1001:0 /app/.output .output

EXPOSE 3000
CMD ["node", ".output/server/index.mjs"]

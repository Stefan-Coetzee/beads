# Stage 1: build the Next.js app (all deps needed for tsc/next build)
FROM node:24-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# Stage 3: minimal runtime image
FROM node:24-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN apk add --no-cache wget

# Next.js standalone reads HOSTNAME to decide which interface to bind.
# In ECS, HOSTNAME defaults to the task hostname (ip-10-0-x-x...); setting
# it to 0.0.0.0 makes the server listen on all interfaces so both the
# container health check (localhost) and ALB health check (container IP) work.
ENV HOSTNAME=0.0.0.0

# next.config.ts output: "standalone" copies everything needed into .next/standalone
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -q --spider http://127.0.0.1:3000/ || exit 1

CMD ["node", "server.js"]

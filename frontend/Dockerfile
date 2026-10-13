# ---------------------------
# 🌐 frontend/Dockerfile - Vue.js + Vite + Tailwind (dev + build)
# ---------------------------
# ---- Dev (Vite + HMR) ----
FROM node:22-alpine AS dev
WORKDIR /app
RUN chown node:node /app
COPY --chown=node:node package*.json ./
USER node
RUN npm ci
COPY --chown=node:node vite.config.ts tsconfig.json tsconfig.node.json postcss.config.cjs ./
COPY --chown=node:node frontend/ ./frontend/
EXPOSE 5173
CMD ["npm","run","dev","--","--host"]

# ---- Build ----
FROM node:22-alpine AS build
WORKDIR /app
RUN chown node:node /app
COPY --chown=node:node package*.json ./
USER node
RUN npm ci
COPY --chown=node:node vite.config.ts tsconfig.json tsconfig.node.json postcss.config.cjs ./
COPY --chown=node:node frontend/ ./frontend/
# >>> Vite environment (build-time) <<<
ARG VITE_API_URL
ARG VITE_TILE_URL
ENV VITE_API_URL=${VITE_API_URL}
ENV VITE_TILE_URL=${VITE_TILE_URL}
# >>> Vite environment (build-time) <<<
RUN npm run build

# ---- Prod (Nginx, non-root) ----
FROM nginxinc/nginx-unprivileged:alpine AS prod
WORKDIR /usr/share/nginx/html
COPY --from=build /app/frontend/dist ./
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY frontend/nginx-security-headers.conf /etc/nginx/conf.d/nginx-security-headers.conf
USER nginx
EXPOSE 8080

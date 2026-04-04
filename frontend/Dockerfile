# ---------------------------
# 🌐 frontend/Dockerfile - Vue.js + Vite + Tailwind (dev + build)
# ---------------------------
# ---- Dev (Vite + HMR) ----
FROM node:20-alpine AS dev
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY vite.config.ts tsconfig.json tsconfig.node.json tailwind.config.ts postcss.config.cjs ./
COPY frontend/ ./frontend/
EXPOSE 5173
CMD ["npm","run","dev","--","--host"]

# ---- Build ----
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY vite.config.ts tsconfig.json tsconfig.node.json tailwind.config.ts postcss.config.cjs ./
COPY frontend/ ./frontend/
# >>> Vite environment (build-time) <<<
ARG VITE_API_URL
ARG VITE_TILE_URL
ENV VITE_API_URL=${VITE_API_URL}
ENV VITE_TILE_URL=${VITE_TILE_URL}
# >>> Vite environment (build-time) <<<
RUN npm run build

# ---- Prod (Nginx) ----
FROM nginx:alpine AS prod
WORKDIR /usr/share/nginx/html
COPY --from=build /app/frontend/dist ./
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80

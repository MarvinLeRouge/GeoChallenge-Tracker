# ---------------------------
# 🌐 frontend/Dockerfile - Vue.js + Vite + Tailwind (dev + build)
# ---------------------------
# ---- Dev (Vite + HMR) ----
FROM node:20-alpine AS dev
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
EXPOSE 5173
CMD ["npm","run","dev","--","--host"]

# ---- Build ----
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# ---- Prod (Nginx) ----
FROM nginx:alpine AS prod
WORKDIR /usr/share/nginx/html
COPY --from=build /app/dist ./
COPY nginx.conf /etc/nginx/conf.d/default.conf

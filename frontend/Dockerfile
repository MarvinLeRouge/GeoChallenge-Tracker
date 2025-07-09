    # ---------------------------
    # 🌐 frontend/Dockerfile - Vue.js + Vite + Tailwind (dev + build)
    # ---------------------------
    FROM node:20-alpine AS build
    
    WORKDIR /app
    
    # Dépendances
    COPY package*.json ./
    RUN npm install
    
    # Copie des sources
    COPY . .

    # Build
    RUN npm run build
    
    # Phase de production Nginx
    FROM nginx:alpine
    WORKDIR /usr/share/nginx/html
    COPY --from=build /app/dist ./
    COPY nginx.conf /etc/nginx/conf.d/default.conf
    
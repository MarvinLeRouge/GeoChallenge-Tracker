# ---------------------------
# 🌐 Dockerfile - Frontend (Vue.js avec Vite)
# ---------------------------
    FROM node:20-alpine as build

    WORKDIR /app
    COPY frontend/package*.json ./
    RUN npm install
    COPY frontend/ .
    RUN npm run build
    
    # Etape de production
    FROM nginx:alpine
    COPY --from=build /app/dist /usr/share/nginx/html
    COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
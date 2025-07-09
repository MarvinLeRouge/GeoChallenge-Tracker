# ---------------------------
# 🌐 frontend/Dockerfile - Étape Nginx de test (servir public/index.html)
# ---------------------------
    FROM nginx:alpine

    WORKDIR /usr/share/nginx/html
    COPY public/ ./
    COPY nginx.conf /etc/nginx/conf.d/default.conf
    
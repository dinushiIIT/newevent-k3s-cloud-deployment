FROM nginx:1.27-alpine
COPY frontend/site/ /usr/share/nginx/html/
EXPOSE 80

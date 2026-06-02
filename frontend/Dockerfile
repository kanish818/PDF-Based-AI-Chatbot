FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json .
RUN npm install
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /opt/documind/nginx.conf.template
COPY start-nginx.sh /opt/documind/start-nginx.sh
RUN chmod +x /opt/documind/start-nginx.sh
EXPOSE 80
CMD ["/opt/documind/start-nginx.sh"]

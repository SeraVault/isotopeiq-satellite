FROM nginx:alpine

# openssl is needed to generate a self-signed certificate on first start
RUN apk add --no-cache openssl

COPY docker-entrypoint.sh /docker-entrypoint.sh
COPY conf.d/default.conf   /etc/nginx/conf.d/default.conf

RUN chmod +x /docker-entrypoint.sh

EXPOSE 80 443

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]

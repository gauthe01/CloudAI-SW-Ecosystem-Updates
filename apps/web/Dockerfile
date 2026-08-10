FROM node:24-alpine

WORKDIR /app

ENV NEXT_TELEMETRY_DISABLED=1 \
    NODE_ENV=production \
    PORT=3000

COPY node_modules ./node_modules
COPY apps/web/package.json ./package.json
RUN ln -sfn .pnpm/node_modules/next ./node_modules/next \
    && ln -sfn .pnpm/node_modules/react ./node_modules/react \
    && ln -sfn .pnpm/node_modules/react-dom ./node_modules/react-dom
COPY apps/web/.next ./.next
COPY apps/web/public ./public

EXPOSE 3000

CMD ["./node_modules/.pnpm/node_modules/.bin/next", "start", "--hostname", "0.0.0.0"]

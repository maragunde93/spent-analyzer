FROM node:24-alpine AS build
WORKDIR /app
ARG VITE_APP_BASE=/
ARG VITE_API_BASE=/api
ARG VITE_ENABLE_API_FALLBACKS=false
ENV VITE_APP_BASE=$VITE_APP_BASE
ENV VITE_API_BASE=$VITE_API_BASE
ENV VITE_ENABLE_API_FALLBACKS=$VITE_ENABLE_API_FALLBACKS
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN npm install -g pnpm@10.15.1 && pnpm install --frozen-lockfile
COPY . .
RUN pnpm build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80

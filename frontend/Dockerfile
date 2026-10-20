FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY . .
RUN npm run build

# Контейнер копирует собранный SPA в общий том и завершает работу.
CMD ["cp", "-r", "/app/build/.", "/frontend_static/"]

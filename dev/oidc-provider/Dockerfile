FROM node:22-alpine
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --no-audit --no-fund
COPY server.js accounts.json ./
EXPOSE 5556
USER node
CMD ["node", "server.js"]

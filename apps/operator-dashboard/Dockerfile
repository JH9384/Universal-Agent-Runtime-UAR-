# UAR Mission Control Dashboard
FROM node:24-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

EXPOSE 3001

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "3001"]

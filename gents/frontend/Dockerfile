# Frontend Dockerfile
FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy source code
COPY . .

# Build app
RUN npm run build

# Install serve to run the build
RUN npm install -g serve

# Expose port
EXPOSE 3000

# Start app
CMD ["serve", "-s", "build", "-l", "3000"]
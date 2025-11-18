FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Use npm install instead of npm ci (more forgiving)
RUN npm install --silent

# Copy source code
COPY . .

# Verify the structure
RUN ls -la /app/src/ && ls -la /app/public/

# Expose port
EXPOSE 3000

# Start development server
CMD ["npm", "start"]
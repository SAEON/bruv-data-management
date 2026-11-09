FROM node:22-alpine

WORKDIR /app

# Copy dependency manifests
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy application source code
COPY . .

# Expose Vite dev server port
EXPOSE 5173

# Start the Vite development server binding to all network interfaces
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]


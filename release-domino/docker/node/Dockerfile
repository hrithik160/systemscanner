FROM node:20-slim

# Ensure uid 1000:1000 has a valid home/cache in /tmp for read-only container execution
ENV HOME=/tmp \
    NPM_CONFIG_CACHE=/tmp/.npm \
    NODE_ENV=development

RUN npm install -g jest@29.7.0
WORKDIR /workspace
USER 1000:1000
CMD ["jest", "--coverage", "--coverageReporters=json-summary"]

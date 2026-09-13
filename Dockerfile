# Build the React surface separately so the runtime image contains only the
# compiled UI and the small FastAPI service.
FROM node:22-alpine AS web-build
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    REENTRY_MODE=demo \
    PORT=8080
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY backend/ ./backend/
RUN python -m pip install --no-cache-dir .
COPY --from=web-build /web/dist ./frontend/dist
EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8080"]


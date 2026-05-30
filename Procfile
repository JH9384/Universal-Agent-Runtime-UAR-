api: uvicorn uar.api.server:app --host 127.0.0.1 --port ${API_PORT:-8000}
web: cd apps/web && npm run dev -- --port ${WEB_PORT:-5173} --host 127.0.0.1
dashboard: cd apps/operator-dashboard && npm run dev

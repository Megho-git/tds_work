# TDS Config Precedence API

A minimal FastAPI service for the TDS config-precedence assignment.

## Deploy on Render

1. Push these files to a GitHub repository you control.
2. In Render, choose **New → Blueprint** and select that repository (or create a Web Service with the settings below).
3. Blueprint deployment reads `render.yaml` automatically. For manual setup use:
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. After deployment succeeds, test `https://YOUR-SERVICE.onrender.com/effective-config`.
5. Submit that endpoint URL, including `/effective-config`, to the course page.

The service merges configuration in this order: hardcoded defaults, `config.<APP_ENV>.yaml`, `.env`, `APP_*` OS environment variables, then repeated `set=key=value` query parameters. The `NUM_WORKERS` alias is supported in `.env`. `api_key` is always masked.

The provided API keys are assignment placeholders, not production secrets.

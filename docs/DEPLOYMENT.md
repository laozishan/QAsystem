# Deployment Guide

This project is designed as a two-service deployment:

- Backend: Railway, root directory `backend`
- Frontend: Vercel, root directory `frontend`

## 1. Deploy the Backend on Railway

1. Open Railway and create a new project.
2. Choose `Deploy from GitHub repo`.
3. Select `laozishan/QAsystem`.
4. Set the service root directory to `backend`.
5. Railway will use `backend/railway.json` and `backend/Dockerfile`.
6. Add environment variables:

```bash
OPENAI_API_KEY=your_openai_key
OPENAI_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
BACKEND_CORS_ORIGINS=https://your-vercel-domain.vercel.app
```

7. After deploy, open the service Networking tab and generate a public domain.
8. Confirm this endpoint works:

```bash
https://your-railway-domain.up.railway.app/api/health
```

For persistent uploaded documents across redeploys, add a Railway volume mounted at `/app/data`.

## 2. Deploy the Frontend on Vercel

1. Import `laozishan/QAsystem` into Vercel.
2. Set the project root directory to `frontend`.
3. Framework preset should be Next.js.
4. Add environment variable:

```bash
NEXT_PUBLIC_API_BASE_URL=https://your-railway-domain.up.railway.app
```

5. Deploy.

## 3. Connect CORS

After Vercel gives you the final domain, return to Railway and update:

```bash
BACKEND_CORS_ORIGINS=https://your-vercel-domain.vercel.app
```

Redeploy the backend so browser requests from Vercel are allowed.


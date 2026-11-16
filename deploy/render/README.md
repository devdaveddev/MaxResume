# Free deployment on Render

The whole app (UI + API) runs as one free Render web service from
[`deploy/render/Dockerfile`](Dockerfile), described by [`render.yaml`](../../render.yaml).

## What the free image keeps and drops

| | Free (Render) | Full (Docker Compose / local) |
|---|---|---|
| Matching engine and scores | identical | identical |
| PDF, DOCX, TXT, scanned PDFs (OCR) | ✅ | ✅ |
| `.odt` | ✅ (read natively) | ✅ |
| `.doc` | ✅ via antiword (page headers not read) | ✅ via LibreOffice |
| `.rtf` | ❌ clear "upload PDF/DOCX" message | ✅ |
| Batch size | 30 files | 50 files |
| Memory | fits 512 MB | ~1 GB |

## Steps (about 10 minutes, no credit card)

1. Sign up at <https://render.com> with your GitHub account.
2. **New → Blueprint**, choose the `MaxResume` repository, click **Apply**.
   Render reads `render.yaml`, builds the Docker image (~8 minutes the first time) and gives you a URL
   like `https://maxresume.onrender.com`.
3. Optional: in the service's **Environment** tab set
   - `MONGO_URL`: a free MongoDB Atlas connection string, so data survives restarts;
   - `API_KEYS`: `name:key` pairs to require an API key.

Every push to `main` redeploys automatically.

## Free-tier behaviour

- The service **sleeps after ~15 minutes without traffic**; the next visit takes about a minute to wake it.
  Open the link a minute before a demo.
- Without `MONGO_URL`, data is in memory and resets when the service restarts or sleeps. Sample data is one
  click away in the UI.
- The demo is public: don't upload real personal data unless `API_KEYS` is set.

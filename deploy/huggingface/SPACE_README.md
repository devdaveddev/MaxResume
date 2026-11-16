---
title: MaxResume
emoji: 📄
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
short_description: AI resume matching & ranking with explainable scores
---

# MaxResume: AI resume matching & candidate ranking

Paste a job description, upload a batch of resumes (PDF, DOCX, DOC, ODT, RTF, TXT; scanned PDFs are
OCR'd), and get a ranked shortlist where every 0–100 score is explained.

**Try it:** pick a sample job description, click **Add sample resumes**, then **Analyse**.
All sample resumes are synthetic.

Source code, architecture and the scoring method: https://github.com/devdaveddev/MaxResume

> Demo deployment: data is kept in memory and resets when the Space restarts. Please don't upload
> real personal data here.

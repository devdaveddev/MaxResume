# Matching algorithm & scoring methodology

This document explains, step by step, how MaxResume turns a job description (JD)
and a resume into a **0–100 match score** and the reasons shown to recruiters.
All constants live in [`backend/app/matching/scorer.py`](../backend/app/matching/scorer.py).

---

## 1. Pipeline overview

```
 JD text ──► JD parser ──────────────┐
                                      ├──► Scorer ──► score (0–100) + breakdown + reasons
 PDF/DOCX ─► text extraction ─► resume parser ┘
```

| Stage | Techniques |
|---|---|
| Text extraction | type sniffed from bytes; `pdfplumber` with per-page two-column detection and **Tesseract OCR** for scanned pages; `python-docx` walking paragraphs, tables, text boxes, headers/footers and hyperlinks in document order; `.doc/.rtf/.odt` via LibreOffice; Unicode/CRLF/bullet/soft-hyphen normalisation (details in [OPERATIONS.md](OPERATIONS.md#3-resume-ingestion-safeguards)) |
| Contacts | email validation; phones via **libphonenumber** (E.164); LinkedIn/GitHub from text *and* embedded links |
| Section detection | heading dictionary (`Experience`, `Technical Skills:`, `Nice to have`…), tolerant of case, punctuation and inline headings |
| Skill extraction | curated taxonomy of ~105 canonical skills with ~280 aliases (`k8s` → Kubernetes, `Postgres` → PostgreSQL), boundary-aware regex, longest-match-first span claiming |
| Entities | regex (email, phone, LinkedIn/GitHub), layout heuristics + **spaCy NER** fallback for name/location |
| Work history | date-range detection (`Mar 2019 – Present`, `03/2019 - 06/2022`, `Jan '19 – Feb '22`, `Since March 2022`, `Summer 2019`), title/company recovery from surrounding lines, gaps and overlaps |
| Parse quality | 10 checks → 0–100 confidence; low-confidence parses are flagged for a human (they are **not** penalised in the score) |
| Semantic matching | **`all-MiniLM-L6-v2`** sentence embeddings (384-d, cosine similarity), run on **ONNX Runtime** from the model's official ONNX export; identical to sentence-transformers on PyTorch (verified by `scripts/compare_engines.py`: 0.00-point score difference on all 28 candidate×JD pairs) at half the memory |

---

## 2. Parsing the job description

The JD parser ([`jd_parser.py`](../backend/app/nlp/jd_parser.py)) produces:

* **Required vs preferred skills** — decided in two layers:
  1. section headings (`Requirements` vs `Nice to have / Preferred / Bonus`);
  2. line-level cues anywhere (`… is a plus`, `preferably`, `familiarity with`, `exposure to`)
     demote that line to *preferred*. A skill present in both lists stays *required*.
* **Alternatives** — `Jenkins or GitHub Actions` becomes one requirement satisfied by either.
* **"or similar"** — `Kafka or similar message brokers` lets a substitute (RabbitMQ) earn near-full credit.
* **Experience** — `5+ years`, `3–5 years`, `minimum of 4 yrs` near the word *experience*; the most demanding one wins.
* **Education** — lowest degree level mentioned (`Bachelor's or Master's` → Bachelor's), field(s),
  "or related field" (accepts other technical degrees) and "or equivalent experience" flags.
* **Requirement statements** — the responsibility/requirement sentences, used for semantic matching.
  Years/degree lines are excluded here because they have their own components (no double counting).
* Company blurb and benefits sections are ignored.

Recruiters can correct any of this in the UI; saving re-scores every candidate.

---

## 3. Parsing a resume

[`resume_parser.py`](../backend/app/nlp/resume_parser.py) extracts name, contact details, location,
summary, skills (with *where* they appear), roles, education, certifications, and "chunks".

**Skills carry evidence flags:**

* `listed` – appears in a skills section;
* `used_in_experience` – appears in the experience or projects text (stronger evidence).

The education section is excluded from skill extraction (so the degree "Electronics and
**Communication**" is not read as the soft skill *Communication*).

**Total experience** is the *union* of all role intervals, so overlapping jobs are not double counted:

```
Job A: Jan 2020 – Dec 2021  (24 months)
Job B: Jan 2021 – Dec 2022  (24 months, 12 overlapping)
Total = 36 months = 3.0 years      (not 4.0)
```

**Chunks** are sentence/bullet-sized pieces of the summary, experience and projects (PDF line-wraps are
re-joined first). The bare skills list is *not* chunked: it is already scored by the skills components,
and semantic evidence should reflect what the candidate actually *did*.

---

## 4. The score

```
score = Σ  wᵢ · sᵢ  × 100        where sᵢ ∈ [0, 1] and Σ wᵢ = 1
```

| Component (i) | Default weight | sᵢ measures |
|---|---:|---|
| Required skills | 0.40 | weighted coverage of must-have skills |
| Relevant experience | 0.20 | effective years vs the JD minimum |
| Semantic fit | 0.20 | how well resume sentences cover JD requirement statements |
| Preferred & soft skills | 0.10 | coverage of nice-to-have skills (soft skills at half weight) |
| Education | 0.10 | degree level and field |

**Re-normalisation.** If the JD does not specify a component (no years, no degree, no preferred skills),
that component is dropped and the remaining weights are scaled to sum to 1. A candidate is never
penalised for a requirement that does not exist. Weights are adjustable per job in the UI.

### 4.1 Skill credit (required and preferred)

Each JD skill gets the **best** credit available, in this order:

| Evidence | Credit | Example |
|---|---:|---|
| Named **and** used in work experience/projects | **1.00** | "Built Spring Boot services…" |
| Named only in a skills list | **0.85** | Skills: Git |
| Implied by a tool that requires it | **0.85** | GitLab CI ⇒ CI/CD, PostgreSQL ⇒ SQL, Spring Boot ⇒ Spring |
| Substitute from the same family, JD says "or similar" | **0.85** | RabbitMQ for "Kafka or similar" |
| Substitute from the same family | **0.50** | MySQL for PostgreSQL, GCP for AWS |
| **Semantically implied** (no keyword at all) | **0.50** | "real-time event streaming platform that publishes and consumes messages" ⇒ Kafka (cos 0.77) |
| Nothing | 0 | |

`s_required = Σ credit / number of required items` (an `A or B` group counts as one item).

**Semantic skill inference.** For each JD skill the resume does not name, we embed a short description
(e.g. *"Kafka: event streaming platform, publishing and consuming messages between services"*) and take the
maximum cosine similarity against all resume chunks. A threshold of **0.62** was calibrated on the sample
set: it accepts the streaming-platform sentence for Kafka (0.77) and rejects "Containerised services with
Docker" for Kubernetes (0.60).

### 4.2 Relevant experience

Each role is classified **relevant** if any of these holds:

* its title is similar to the JD title (cosine ≥ 0.60), or
* its title + description is similar to the JD requirements (cosine ≥ 0.50), or
* it mentions at least a quarter of the JD's required skills (minimum 2).

On the sample set every backend role scored ≥ 0.50 on description, while frontend, data-science and QA
roles scored ≤ 0.44, so the thresholds sit in a clear gap.

```
effective_years = relevant_years + 0.5 × (total_years − relevant_years)
s_experience    = min(1, effective_years / required_min_years)
```

Unrelated experience still counts half: it shows professional maturity but not domain fit.
Being above the JD's maximum is flagged ("may be overqualified") but **not** penalised.

### 4.3 Semantic fit

For every JD requirement statement *r*, find the most similar resume chunk *c*:

```
sim(r) = max_c cos(embed(r), embed(c))
coverage(r) = clip((sim(r) − 0.25) / (0.70 − 0.25), 0, 1)
s_semantic  = mean_r coverage(r)
```

MiniLM similarities for "same meaning, different words" sit around 0.55–0.75 and unrelated pairs around
0.0–0.25, so the linear map spreads real matches across the full 0–1 range. The best pairs and the
weakest requirements are shown to the recruiter as evidence.

### 4.4 Education

```
level  = 1.0 if candidate ≥ required, 0.5 if one level below, else 0
         (0.7 if the JD accepts "equivalent experience" and effective years ≥ min + 2)
field  = 1.0 if the field is accepted, 0.3 if a degree in another field, else 0
s_education = 0.75 × level + 0.25 × field
```

---

## 5. Worked example — Daniel Okafor vs "Senior Java Backend Engineer"

**Required skills** (15 items, `Jenkins / GitHub Actions` counted as one):

| Credit | Skills |
|---|---|
| 1.00 × 7 | Java, Spring Boot, REST APIs, SQL, PostgreSQL, Docker, Kubernetes |
| 0.85 × 2 | CI/CD (implied by GitLab CI), Git (listed) |
| 0.50 × 3 | Kafka (semantically implied), AWS (has GCP), Jenkins / GitHub Actions (has GitLab CI) |
| 0 × 3 | Microservices, JUnit, Agile |

s = (7 + 1.7 + 1.5) / 15 = **0.680**

**Preferred & soft**: 6 preferred (weight 1) + 2 soft skills (weight 0.5) = total weight 7.
Kotlin 1.0 + GraphQL 0.5 (has gRPC, same API-style family) = 1.5 → s = 1.5 / 7 = **0.214**

**Experience**: 6.5 years, both roles relevant → effective 6.5 ≥ 5 → s = **1.0**

**Semantic fit**: mean coverage over 14 requirement statements → s = **0.409**

**Education**: B.Eng Software Engineering; JD wants a Bachelor's in CS or a related field → s = **1.0**

| Component | Weight | sᵢ | Points |
|---|---:|---:|---:|
| Required skills | 0.40 | 0.680 | 27.2 |
| Relevant experience | 0.20 | 1.000 | 20.0 |
| Semantic fit | 0.20 | 0.409 | 8.2 |
| Preferred & soft | 0.10 | 0.214 | 2.1 |
| Education | 0.10 | 1.000 | 10.0 |
| **Total** | | | **67.5 % → "Good match"** |

Verdict bands: ≥ 80 Strong · 65–80 Good · 50–65 Partial · < 50 Weak.

---

## 6. Why this design

* **Hybrid, not pure embeddings.** A single resume↔JD cosine is opaque and unstable (long documents
  dilute meaning). Explicit skill coverage is precise and explainable; embeddings are used where they
  shine: catching paraphrases ("event streaming" ≈ Kafka) and judging role relevance.
* **Every number has a reason.** Each component returns its evidence (matched text, similarities,
  role classifications), and the reasons list is generated from that evidence, not written separately.
* **Recruiter in the loop.** Extracted requirements and weights are editable; re-scoring is instant
  because parsed profiles are stored and only the scorer re-runs.
* **Runs locally on CPU.** MiniLM is ~90 MB, encodes a 14-resume batch in a few seconds, and needs no API keys.

## 7. Known limitations

* The skills taxonomy is curated (tech-focused); skills outside it are only caught semantically.
* Scanned/image-only PDFs are rejected (no OCR).
* Thresholds were calibrated on a small synthetic set; a production system would tune them on labelled
  recruiter decisions.
* Multi-column PDF layouts can interleave text; DOCX tables are handled.

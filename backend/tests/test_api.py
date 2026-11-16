from fastapi.testclient import TestClient

from app.main import app


def test_end_to_end(samples):
    with TestClient(app) as c:
        jd = (samples / "job_descriptions" / "senior_java_backend_engineer.txt").read_text()
        job = c.post("/api/jobs", data={"text": jd}).json()
        files = [("files", (p.name, p.read_bytes())) for p in sorted((samples / "resumes").iterdir())]
        files.append(("files", ("broken.pdf", b"%PDF-1.4 not really a pdf")))
        res = c.post(f"/api/jobs/{job['id']}/resumes", files=files).json()
        assert len(res["added"]) >= 10
        assert res["errors"] and res["errors"][0]["filename"] == "broken.pdf"

        rows = c.get(f"/api/jobs/{job['id']}/candidates").json()
        assert [r["rank"] for r in rows] == list(range(1, len(rows) + 1))
        assert rows[0]["score"] >= rows[-1]["score"]

        detail = c.get(f"/api/candidates/{rows[0]['id']}").json()
        assert detail["match"]["reasons"] and detail["profile"]["experience"]

        before = rows[0]["score"]
        c.put(f"/api/jobs/{job['id']}", json={"min_years": 15})
        after = c.get(f"/api/candidates/{rows[0]['id']}").json()["match"]["score"]
        assert after < before  # stricter requirement -> rescored lower

        assert c.delete(f"/api/jobs/{job['id']}").status_code == 204

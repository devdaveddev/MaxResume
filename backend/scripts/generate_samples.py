"""Generate synthetic sample data: 2 job descriptions + 14 fictional resumes.

All people, companies and contact details are invented (emails use
example.com, phone numbers use the 555 range). Resumes are rendered as a mix
of PDF and DOCX with three different experience-header layouts so the parser
is exercised on varied formatting:

  layout A:  "Title | Company | Jan 2020 – Present"           (single line)
  layout B:  "Company, City    Jan 2020 - Mar 2023" / "Title"   (company first)
  layout C:  "Title" / "Company | 01/2020 - 03/2023"            (numeric dates)

Run:  uv run python scripts/generate_samples.py
"""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.shared import Pt
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

ROOT = Path(__file__).resolve().parents[2] / "sample_data"

JAVA_JD = """Senior Java Backend Engineer
Location: Bengaluru (Hybrid)

About Us
Northwind Labs builds payment infrastructure used by thousands of merchants. We value ownership, clear communication and pragmatic engineering.

Key Responsibilities
Design, build and maintain scalable microservices using Java and Spring Boot.
Develop RESTful APIs consumed by web and mobile clients.
Build event-driven systems using Apache Kafka for real-time payment processing.
Optimize SQL queries and database schemas in PostgreSQL for high-throughput workloads.
Deploy and operate services on AWS using Docker and Kubernetes.
Write unit and integration tests with JUnit and participate in code reviews.
Mentor junior engineers and collaborate with product managers in an Agile team.

Requirements
5+ years of professional experience in backend software development.
Strong proficiency in Java 17 and the Spring Boot ecosystem.
Hands-on experience with microservices architecture and REST APIs.
Solid knowledge of SQL and relational databases such as PostgreSQL.
Experience with Kafka or similar message brokers.
Experience with Docker, Kubernetes and CI/CD pipelines (Jenkins or GitHub Actions).
Working knowledge of AWS cloud services.
Proficiency with Git.
Bachelor's degree in Computer Science or a related field, or equivalent practical experience.
Good communication and problem-solving skills.

Nice to Have
Experience with Redis caching.
Familiarity with Terraform or other infrastructure-as-code tools.
Knowledge of GraphQL.
Exposure to Kotlin.
Experience with observability tools like Prometheus and Grafana.

What We Offer
Competitive salary, health insurance and a learning budget.
"""

DS_JD = """Job Title: Data Scientist

About the company
Brightpath Analytics helps retailers forecast demand.

Responsibilities
Build and deploy machine learning models for demand forecasting and customer segmentation.
Analyze large datasets with Python, Pandas and SQL to generate business insights.
Design A/B tests and apply statistical analysis to evaluate product changes.
Work with data engineers to build reliable ETL data pipelines.
Communicate findings to non-technical stakeholders with clear dashboards.

Requirements
3+ years of experience as a Data Scientist or in a similar analytical role.
Strong Python skills including Pandas, NumPy and scikit-learn.
Solid understanding of statistics and machine learning.
Experience writing complex SQL queries.
Master's degree in Statistics, Computer Science, Mathematics or a related field.

Preferred
Experience with deep learning frameworks such as PyTorch or TensorFlow.
Experience with Spark is a plus.
Familiarity with Tableau or Power BI.
"""

# --------------------------------------------------------------------------- candidates
# Each role: (title, company, city, start, end, [bullets]); dates are strings in "Mon YYYY" form.
CANDIDATES = [
    dict(file="aarav_mehta.pdf", layout="A", name="Aarav Mehta", email="aarav.mehta@example.com",
         phone="+91 98765 55501", location="Bengaluru, India", linkedin="linkedin.com/in/aarav-mehta-demo",
         summary="Backend engineer with 7 years of experience building high-throughput payment and fintech platforms in Java.",
         skills="Java, Spring Boot, Microservices, REST APIs, Kafka, PostgreSQL, Redis, Docker, Kubernetes, AWS, Jenkins, JUnit, Git, Agile",
         roles=[("Senior Software Engineer", "Finlytics Payments", "Bengaluru", "Apr 2022", "Present", [
             "Led the design of 14 Spring Boot microservices processing 3M payment transactions per day.",
             "Built event-driven settlement pipeline on Apache Kafka, cutting reconciliation time by 60%.",
             "Migrated services to Kubernetes (EKS) on AWS with Docker and Jenkins CI/CD pipelines.",
             "Tuned PostgreSQL queries and added Redis caching, reducing p99 latency from 480ms to 90ms.",
             "Mentored 4 junior engineers and ran code reviews."]),
             ("Software Engineer", "Kestrel Commerce", "Pune", "Jul 2019", "Mar 2022", [
             "Developed RESTful APIs in Java 11 and Spring Boot for an order management platform.",
             "Wrote JUnit and Mockito tests, raising coverage from 45% to 82%.",
             "Designed PostgreSQL schemas and SQL reporting queries."])],
         education=[("B.Tech in Computer Science", "National Institute of Technology, Trichy", "2019")],
         certs=["AWS Certified Developer – Associate"]),

    dict(file="sofia_ramirez.docx", layout="B", name="Sofia Ramirez", email="sofia.ramirez@example.com",
         phone="+1 555 010 2234", location="Austin, TX", linkedin="linkedin.com/in/sofia-ramirez-demo",
         summary="Java developer with 5 years of experience delivering REST services for logistics and retail.",
         skills="Java, Spring Boot, Hibernate, MySQL, RabbitMQ, Docker, Azure, Git, JUnit, Maven, Scrum",
         roles=[("Java Developer", "Cargo Trail Systems", "Austin", "Feb 2023", "Present", [
             "Build Spring Boot REST APIs for shipment tracking used by 200+ warehouses.",
             "Implemented asynchronous order events with RabbitMQ and Docker containers deployed to Azure.",
             "Optimized MySQL indexes and Hibernate mappings to halve query time."]),
             ("Junior Java Developer", "Retail Grid Inc", "Dallas", "Jan 2021", "Jan 2023", [
             "Maintained a monolithic Java application and extracted two services into microservices.",
             "Wrote unit tests with JUnit and maintained Maven builds."])],
         education=[("M.S. in Computer Science", "University of Texas at Dallas", "2020"),
                    ("B.S. in Information Technology", "Monterrey Institute of Technology", "2018")],
         certs=["Oracle Certified Professional, Java SE 11 Developer"]),

    dict(file="daniel_okafor.pdf", layout="C", name="Daniel Okafor", email="daniel.okafor@example.com",
         phone="+44 555 0193 442", location="London, UK", linkedin=None,
         summary="Backend engineer focused on JVM languages and streaming systems.",
         skills="Kotlin, Java, Spring Boot, PostgreSQL, GCP, Docker, Kubernetes, gRPC, Git",
         roles=[("Backend Engineer", "Streamline Media", "London", "Mar 2022", "Present", [
             "Develop Kotlin and Java services with Spring Boot on Google Cloud (GKE).",
             "Built a real-time event streaming platform that publishes and consumes millions of messages per hour between independently deployable services.",
             "Designed PostgreSQL schemas and wrote complex SQL for analytics endpoints."]),
             ("Software Developer", "Ledgerly", "Manchester", "Jun 2020", "Feb 2022", [
             "Built internal REST endpoints and gRPC services in Java.",
             "Set up GitLab CI pipelines and Docker images for 6 services."])],
         education=[("BEng in Software Engineering", "University of Manchester", "2020")],
         certs=[]),

    dict(file="mei_lin_chen.pdf", layout="A", name="Mei Lin Chen", email="meilin.chen@example.com",
         phone="+65 5550 1122", location="Singapore", linkedin="linkedin.com/in/meilin-chen-demo",
         summary="Software engineer with 4 years of Java experience who enjoys clean code and testing.",
         skills="Java, Spring Boot, SQL, MySQL, Git, JUnit, HTML, CSS",
         roles=[("Software Engineer", "Harbor Fintech", "Singapore", "Aug 2023", "Present", [
             "Develop Spring Boot REST APIs for loan origination.",
             "Write SQL queries and stored procedures in MySQL.",
             "Write JUnit tests and fix production bugs."]),
             ("Graduate Software Engineer", "Bluefin Systems", "Singapore", "Aug 2022", "Jul 2023", [
             "Built internal admin pages and Java batch jobs."])],
         education=[("B.E. in Computer Engineering", "Nanyang Technological University", "2022")],
         certs=[]),

    dict(file="rohan_iyer.docx", layout="C", name="Rohan Iyer", email="rohan.iyer@example.com",
         phone="+91 99001 55502", location="Hyderabad, India", linkedin="linkedin.com/in/rohan-iyer-demo",
         summary="Principal engineer with 11 years of experience architecting distributed Java systems.",
         skills="Java, Spring Boot, Spring Framework, Microservices, Kafka, Kubernetes, Docker, AWS, Terraform, Redis, PostgreSQL, Cassandra, GraphQL, Prometheus, Grafana, GitHub Actions, Leadership",
         roles=[("Principal Engineer", "Orbit Pay", "Hyderabad", "Jan 2021", "Present", [
             "Architected a microservices platform of 40+ Spring Boot services on AWS EKS managed with Terraform.",
             "Introduced Kafka-based event sourcing and Redis caching for the ledger, supporting 10k TPS.",
             "Set up Prometheus and Grafana observability and GitHub Actions CI/CD.",
             "Led a team of 12 engineers across two squads."]),
             ("Senior Software Engineer", "Telstar Networks", "Bengaluru", "Jun 2017", "Dec 2020", [
             "Built REST and GraphQL APIs in Java with Spring Framework and PostgreSQL.",
             "Migrated a Cassandra cluster and wrote performance-critical multithreaded Java code."]),
             ("Software Engineer", "Infowave Solutions", "Chennai", "Jul 2015", "May 2017", [
             "Developed Java J2EE modules and SQL reports for a banking client."])],
         education=[("M.Tech in Computer Science", "Indian Institute of Technology, Madras", "2015")],
         certs=["Certified Kubernetes Administrator (CKA)"]),

    dict(file="emily_novak.pdf", layout="B", name="Emily Novak", email="emily.novak@example.com",
         phone="+1 555 014 7788", location="Seattle, WA", linkedin="linkedin.com/in/emily-novak-demo",
         summary="Backend engineer with 6 years of experience building Python web services.",
         skills="Python, Django, FastAPI, PostgreSQL, Redis, Docker, Kubernetes, AWS, Celery, Git, PyTest, REST APIs",
         roles=[("Senior Backend Engineer", "Cloudberry Health", "Seattle", "May 2022", "Present", [
             "Design Django and FastAPI REST APIs serving 5M requests per day.",
             "Run services on AWS with Docker and Kubernetes; built GitHub Actions CI/CD pipelines.",
             "Model PostgreSQL schemas and optimize slow SQL queries."]),
             ("Backend Engineer", "Tidewater Apps", "Portland", "Sep 2020", "Apr 2022", [
             "Built Python microservices and background workers with Celery and Redis.",
             "Wrote PyTest suites and maintained 90% coverage."])],
         education=[("B.S. in Computer Science", "Oregon State University", "2020")],
         certs=[]),

    dict(file="karan_desai.docx", layout="A", name="Karan Desai", email="karan.desai@example.com",
         phone="+91 98111 55503", location="Mumbai, India", linkedin=None,
         summary="Frontend developer passionate about user interfaces and design systems.",
         skills="JavaScript, TypeScript, React, Redux, Next.js, HTML, CSS, Tailwind CSS, Node.js, Jest, Git",
         roles=[("Frontend Developer", "Pixelcraft Studio", "Mumbai", "Jun 2023", "Present", [
             "Build React and TypeScript dashboards with Redux and Tailwind CSS.",
             "Created a shared component library used by 5 product teams."]),
             ("Web Developer Intern", "Brightside Media", "Mumbai", "Jan 2023", "May 2023", [
             "Built landing pages with Next.js and a small Node.js API."])],
         education=[("B.Sc in Information Technology", "University of Mumbai", "2022")],
         certs=[]),

    dict(file="hannah_weber.pdf", layout="C", name="Hannah Weber", email="hannah.weber@example.com",
         phone="+49 555 1234 567", location="Berlin, Germany", linkedin="linkedin.com/in/hannah-weber-demo",
         summary="Software engineer who moved from quality assurance into Java backend development.",
         skills="Java, Spring Boot, REST APIs, SQL, Oracle DB, Selenium, Jira, Git, Jenkins, Docker",
         roles=[("Java Backend Developer", "Rheinwerk Insurance", "Berlin", "Feb 2022", "Present", [
             "Develop Spring Boot services for claims processing with Oracle DB.",
             "Containerised legacy services with Docker and Jenkins pipelines.",
             "Expose REST APIs consumed by partner portals."]),
             ("QA Test Analyst", "Nordlicht Software", "Hamburg", "Jan 2016", "Jan 2022", [
             "Performed manual regression testing and wrote Selenium UI test scripts.",
             "Tracked defects in Jira and coordinated release sign-off with business teams."])],
         education=[("B.Sc in Physics", "University of Hamburg", "2015")],
         certs=["ISTQB Certified Tester Foundation Level"]),

    dict(file="arjun_nair.docx", layout="B", name="Arjun Nair", email="arjun.nair@example.com",
         phone="+91 97452 55504", location="Kochi, India", linkedin="linkedin.com/in/arjun-nair-demo",
         summary="Backend developer with 7 years of experience in the Microsoft .NET ecosystem.",
         skills="C#, .NET, ASP.NET Core, SQL Server, Azure, Microservices, Docker, REST APIs, Git, Azure DevOps",
         roles=[("Software Engineer", "Coastal Logistics", "Kochi", "Mar 2021", "Present", [
             "Built ASP.NET Core microservices on Azure Kubernetes Service with Docker.",
             "Designed SQL Server schemas and stored procedures.",
             "Built REST APIs and Azure Service Bus integrations."]),
             ("Associate Developer", "Techverse Solutions", "Trivandrum", "Jun 2019", "Feb 2021", [
             "Maintained C# WinForms and Web API applications."])],
         education=[("B.Tech in Electronics and Communication", "College of Engineering Trivandrum", "2019")],
         certs=["Microsoft Certified: Azure Developer Associate"]),

    dict(file="lucia_fernandes.pdf", layout="A", name="Lucia Fernandes", email="lucia.fernandes@example.com",
         phone="+351 555 210 334", location="Lisbon, Portugal", linkedin="linkedin.com/in/lucia-fernandes-demo",
         summary="Backend engineer with 6 years of experience in Java microservices for e-commerce.",
         skills="Java, Spring Boot, Microservices, Kafka, PostgreSQL, Docker, Kubernetes, Jenkins, JUnit, GCP, Git, REST APIs",
         roles=[("Senior Backend Engineer", "Mercado Atlantico", "Lisbon", "Oct 2022", "Present", [
             "Own checkout microservices written in Java 17 and Spring Boot.",
             "Built Kafka consumers for inventory events and PostgreSQL-backed order store.",
             "Run workloads on Kubernetes (GKE) with Docker and Jenkins CI/CD."]),
             ("Backend Engineer", "Lusitania Digital", "Porto", "Sep 2020", "Sep 2022", [
             "Developed REST APIs in Spring Boot and wrote JUnit tests.",
             "Improved SQL query performance on PostgreSQL."])],
         education=[("B.Tech in Information Technology", "University of Porto", "2020")],
         certs=["Google Associate Cloud Engineer"]),

    dict(file="tom_becker.docx", layout="C", name="Tom Becker", email="tom.becker@example.com",
         phone="+1 555 019 4455", location="Boston, MA", linkedin="linkedin.com/in/tom-becker-demo",
         summary="Data scientist with 6 years of experience in forecasting and experimentation.",
         skills="Python, Pandas, NumPy, scikit-learn, SQL, Statistics, A/B testing, Tableau, Machine Learning, Airflow",
         roles=[("Data Scientist", "Harborview Retail", "Boston", "Jul 2022", "Present", [
             "Built demand forecasting models with scikit-learn, improving forecast accuracy by 18%.",
             "Designed and analysed A/B tests for pricing experiments.",
             "Created Tableau dashboards for merchandising leadership."]),
             ("Data Analyst", "Greenleaf Insurance", "Hartford", "Aug 2020", "Jun 2022", [
             "Wrote complex SQL queries and Python scripts with Pandas for claims analysis.",
             "Maintained Airflow ETL jobs."])],
         education=[("M.S. in Statistics", "Boston University", "2020")],
         certs=[]),

    dict(file="nisha_kapoor.pdf", layout="B", name="Nisha Kapoor", email="nisha.kapoor@example.com",
         phone="+91 98200 55505", location="Delhi, India", linkedin="linkedin.com/in/nisha-kapoor-demo",
         summary="Recent computer science graduate eager to build backend systems in Java.",
         skills="Java, Spring Boot, MySQL, REST APIs, Git, Docker, Data Structures, Algorithms",
         roles=[("Software Engineering Intern", "Zentrix Software", "Delhi", "Jan 2025", "Jun 2025", [
             "Built Spring Boot REST endpoints for an internal HR tool.",
             "Wrote MySQL queries and Dockerized the service."])],
         projects=["Library Management System – Java, Spring Boot and MySQL REST application with JWT authentication.",
                   "Distributed chat server – multithreaded Java sockets."],
         education=[("B.Tech in Computer Science and Engineering", "Delhi Technological University", "2025")],
         certs=[]),

    dict(file="priya_venkatesh.pdf", layout="A", name="Priya Venkatesh", email="priya.venkatesh@example.com",
         phone="+91 99450 55506", location="Chennai, India", linkedin="linkedin.com/in/priya-venkatesh-demo",
         summary="Data scientist with 6 years of experience in NLP and deep learning.",
         skills="Python, PyTorch, TensorFlow, NLP, Machine Learning, Deep Learning, Pandas, NumPy, scikit-learn, SQL, Spark, Statistics, Power BI",
         roles=[("Senior Data Scientist", "Lumen AI Labs", "Chennai", "Jun 2022", "Present", [
             "Train PyTorch transformer models for document classification and NLP.",
             "Built Spark feature pipelines over 2TB of transaction data.",
             "Present model insights to business stakeholders with Power BI."]),
             ("Data Scientist", "Saffron Analytics", "Bengaluru", "Jul 2020", "May 2022", [
             "Built customer segmentation and churn models with scikit-learn and Pandas.",
             "Ran statistical analysis and hypothesis testing for marketing campaigns."])],
         education=[("M.Sc in Statistics", "University of Madras", "2020")],
         certs=["TensorFlow Developer Certificate"]),

    dict(file="marcus_lee.docx", layout="A", name="Marcus Lee", email="marcus.lee@example.com",
         phone="+61 555 432 109", location="Sydney, Australia", linkedin="linkedin.com/in/marcus-lee-demo",
         summary="DevOps engineer with 6 years automating cloud infrastructure.",
         skills="AWS, Kubernetes, Docker, Terraform, Ansible, Jenkins, GitHub Actions, Python, Bash, Linux, Prometheus, Grafana, Java",
         roles=[("DevOps Engineer", "Southern Cross Telecom", "Sydney", "Feb 2022", "Present", [
             "Manage 30 Kubernetes clusters on AWS provisioned with Terraform.",
             "Built CI/CD with Jenkins and GitHub Actions for Java and Python services.",
             "Set up Prometheus and Grafana alerting."]),
             ("Systems Engineer", "Koala Hosting", "Melbourne", "Jan 2020", "Jan 2022", [
             "Automated Linux server provisioning with Ansible and Bash.",
             "Supported Java application deployments on Tomcat."])],
         education=[("Bachelor of Engineering in Computer Systems", "RMIT University", "2019")],
         certs=["AWS Certified SysOps Administrator"]),
]


def _numeric(d: str) -> str:
    if d == "Present":
        return "Present"
    from datetime import datetime

    return datetime.strptime(d, "%b %Y").strftime("%m/%Y")


def _role_header(layout: str, title, company, city, start, end) -> list[str]:
    if layout == "A":
        return [f"{title} | {company} | {start} – {end}"]
    if layout == "B":
        return [f"{company}, {city}    {start} - {end}", title]
    return [title, f"{company} | {_numeric(start)} - {_numeric(end)}"]


def _blocks(c: dict) -> list[tuple[str, str]]:
    """Resume as a list of (style, text): style in name|contact|h|p|b|bold."""
    out = [("name", c["name"])]
    contact = [c["email"], c["phone"], c["location"]] + ([c["linkedin"]] if c.get("linkedin") else [])
    out.append(("contact", " | ".join(contact)))
    out += [("h", "PROFESSIONAL SUMMARY"), ("p", c["summary"])]
    out += [("h", "TECHNICAL SKILLS"), ("p", c["skills"])]
    out.append(("h", "WORK EXPERIENCE"))
    for title, company, city, start, end, bullets in c["roles"]:
        for line in _role_header(c["layout"], title, company, city, start, end):
            out.append(("bold", line))
        out += [("b", b) for b in bullets]
    if c.get("projects"):
        out.append(("h", "PROJECTS"))
        out += [("b", p) for p in c["projects"]]
    out.append(("h", "EDUCATION"))
    for degree, inst, year in c["education"]:
        out += [("bold", degree), ("p", f"{inst} | {year}")]
    if c.get("certs"):
        out.append(("h", "CERTIFICATIONS"))
        out += [("b", x) for x in c["certs"]]
    return out


def write_pdf(c: dict, path: Path) -> None:
    ss = getSampleStyleSheet()
    styles = {
        "name": ParagraphStyle("n", parent=ss["Title"], fontSize=18, spaceAfter=2),
        "contact": ParagraphStyle("c", parent=ss["Normal"], fontSize=9, alignment=1, spaceAfter=6),
        "h": ParagraphStyle("h", parent=ss["Heading3"], spaceBefore=8, spaceAfter=3),
        "p": ParagraphStyle("p", parent=ss["Normal"], fontSize=10, leading=13),
        "bold": ParagraphStyle("bo", parent=ss["Normal"], fontName="Helvetica-Bold", fontSize=10, spaceBefore=4),
        "b": ParagraphStyle("b", parent=ss["Normal"], fontSize=10, leading=13, leftIndent=10),
    }
    story = []
    for style, text in _blocks(c):
        text = text.replace("&", "&amp;").replace("    ", "&nbsp;&nbsp;&nbsp;&nbsp;")
        story.append(Paragraph(("• " if style == "b" else "") + text, styles[style]))
    story.append(Spacer(1, 4 * mm))
    SimpleDocTemplate(str(path), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                      topMargin=14 * mm, bottomMargin=14 * mm, title=f"Resume - {c['name']}").build(story)


def write_docx(c: dict, path: Path) -> None:
    doc = Document()
    doc.styles["Normal"].font.size = Pt(10)
    for style, text in _blocks(c):
        if style == "name":
            doc.add_heading(text, level=0)
        elif style == "h":
            doc.add_heading(text.title(), level=2)
        elif style == "b":
            doc.add_paragraph(text, style="List Bullet")
        elif style == "bold":
            doc.add_paragraph().add_run(text).bold = True
        elif style == "p" and text == c["skills"] and c["layout"] == "C":
            # some templates put skills in a table: exercise table extraction
            items = [s.strip() for s in text.split(",")]
            table = doc.add_table(rows=0, cols=3)
            for i in range(0, len(items), 3):
                cells = table.add_row().cells
                for j, item in enumerate(items[i:i + 3]):
                    cells[j].text = item + ","
        else:
            doc.add_paragraph(text)
    doc.save(str(path))


def main() -> None:
    (ROOT / "resumes").mkdir(parents=True, exist_ok=True)
    (ROOT / "job_descriptions").mkdir(parents=True, exist_ok=True)
    (ROOT / "job_descriptions" / "senior_java_backend_engineer.txt").write_text(JAVA_JD)
    (ROOT / "job_descriptions" / "data_scientist.txt").write_text(DS_JD)
    for c in CANDIDATES:
        path = ROOT / "resumes" / c["file"]
        (write_pdf if path.suffix == ".pdf" else write_docx)(c, path)
    print(f"Wrote {len(CANDIDATES)} resumes and 2 JDs to {ROOT}")


if __name__ == "__main__":
    main()

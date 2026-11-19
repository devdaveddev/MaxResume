"""Curated skills taxonomy.

Each canonical skill maps to:
  * aliases  – surface forms we look for in text (case-insensitive unless listed
               in CASE_SENSITIVE_ALIASES, which protects short/ambiguous words
               such as "Go", "R" or "C").
  * category – used for grouping in the UI.
  * family   – optional. Skills in the same family are *substitutes* for each
               other (PostgreSQL vs MySQL, AWS vs Azure ...). A candidate who has
               a sibling skill gets partial credit instead of zero.

Keeping this as plain Python data (not a DB table) makes it easy to read,
review and extend during the interview.
"""

from __future__ import annotations

_RAW: dict[str, tuple[str, str | None, list[str]]] = {
    "Java": ("Languages", None, ["java", "core java", "java 8", "java 11", "java 17", "java 21", "j2ee", "java ee"]),
    "Python": ("Languages", None, ["python", "python3", "python 3"]),
    "JavaScript": ("Languages", "js-lang", ["javascript", "js", "ecmascript", "es6"]),
    "TypeScript": ("Languages", "js-lang", ["typescript"]),
    "C++": ("Languages", None, ["c++", "cpp"]),
    "C#": ("Languages", None, ["c#", "csharp", "c sharp"]),
    "C": ("Languages", None, ["C"]),
    "Go": ("Languages", None, ["golang", "Go"]),
    "Rust": ("Languages", None, ["rust"]),
    "Kotlin": ("Languages", "jvm-lang", ["kotlin"]),
    "Scala": ("Languages", "jvm-lang", ["scala"]),
    "Ruby": ("Languages", None, ["ruby"]),
    "PHP": ("Languages", None, ["php"]),
    "Swift": ("Languages", None, ["swift"]),
    "R": ("Languages", None, ["R"]),
    "SQL": ("Databases", None, ["sql", "t-sql", "pl/sql", "plsql", "ansi sql"]),
    "Bash": ("Languages", None, ["bash", "shell scripting", "shell script", "unix shell"]),

    "Spring Boot": ("Backend", "java-web", ["spring boot", "springboot", "spring-boot"]),
    "Spring Framework": ("Backend", "java-web", ["spring framework", "spring mvc", "Spring", "spring core"]),
    "Hibernate": ("Backend", "orm", ["hibernate", "jpa", "spring data jpa"]),
    "Django": ("Backend", "py-web", ["django", "django rest framework", "drf"]),
    "Flask": ("Backend", "py-web", ["flask"]),
    "FastAPI": ("Backend", "py-web", ["fastapi", "fast api"]),
    "Node.js": ("Backend", "js-web", ["node.js", "nodejs", "node js"]),
    "Express.js": ("Backend", "js-web", ["express.js", "expressjs", "express framework"]),
    "NestJS": ("Backend", "js-web", ["nestjs", "nest.js"]),
    ".NET": ("Backend", None, [".net", "dotnet", ".net core", "asp.net", "asp.net core"]),
    "Ruby on Rails": ("Backend", None, ["ruby on rails", "rails"]),
    "Microservices": ("Architecture", None, ["microservices", "microservice", "micro-services", "microservice architecture"]),
    "REST APIs": ("Architecture", "api-style", ["REST", "restful", "rest api", "rest apis", "restful api", "restful apis", "restful services", "rest services"]),
    "GraphQL": ("Architecture", "api-style", ["graphql"]),
    "gRPC": ("Architecture", "api-style", ["grpc"]),
    "System Design": ("Architecture", None, ["system design", "distributed systems", "scalable systems", "high availability"]),
    "Design Patterns": ("Architecture", None, ["design patterns", "solid principles", "object oriented design", "ood"]),
    "OOP": ("Architecture", None, ["oop", "object oriented programming", "object-oriented programming", "object-oriented"]),
    "Multithreading": ("Backend", None, ["multithreading", "multi-threading", "concurrency", "concurrent programming"]),
    "Data Structures & Algorithms": ("Fundamentals", None, ["data structures", "algorithms", "dsa"]),

    "React": ("Frontend", "spa", ["react", "react.js", "reactjs"]),
    "Angular": ("Frontend", "spa", ["angular", "angularjs", "angular.js"]),
    "Vue.js": ("Frontend", "spa", ["vue", "vue.js", "vuejs"]),
    "Next.js": ("Frontend", None, ["next.js", "nextjs"]),
    "Redux": ("Frontend", None, ["redux", "redux toolkit"]),
    "HTML": ("Frontend", None, ["html", "html5"]),
    "CSS": ("Frontend", None, ["css", "css3", "scss", "sass"]),
    "Tailwind CSS": ("Frontend", None, ["tailwind", "tailwind css", "tailwindcss"]),

    "PostgreSQL": ("Databases", "rdbms", ["postgresql", "postgres", "psql"]),
    "MySQL": ("Databases", "rdbms", ["mysql", "mariadb"]),
    "Oracle DB": ("Databases", "rdbms", ["oracle", "oracle db", "oracle database"]),
    "SQL Server": ("Databases", "rdbms", ["sql server", "mssql", "ms sql"]),
    "MongoDB": ("Databases", "nosql", ["mongodb", "mongo"]),
    "Cassandra": ("Databases", "nosql", ["cassandra"]),
    "DynamoDB": ("Databases", "nosql", ["dynamodb"]),
    "Redis": ("Databases", "cache", ["redis"]),
    "Elasticsearch": ("Databases", None, ["elasticsearch", "elastic search", "opensearch", "elk"]),

    "Kafka": ("Messaging", "mq", ["kafka", "apache kafka"]),
    "RabbitMQ": ("Messaging", "mq", ["rabbitmq", "rabbit mq"]),
    "ActiveMQ": ("Messaging", "mq", ["activemq"]),
    "AWS SQS": ("Messaging", "mq", ["sqs", "aws sqs"]),

    "AWS": ("Cloud", "cloud", ["aws", "amazon web services", "ec2", "s3", "aws lambda"]),
    "Azure": ("Cloud", "cloud", ["azure", "microsoft azure"]),
    "GCP": ("Cloud", "cloud", ["gcp", "google cloud", "google cloud platform"]),
    "Docker": ("DevOps", "container", ["docker", "containerization", "containers"]),
    "Kubernetes": ("DevOps", "orchestration", ["kubernetes", "k8s", "eks", "aks", "gke", "openshift"]),
    "Terraform": ("DevOps", "iac", ["terraform"]),
    "Ansible": ("DevOps", "iac", ["ansible"]),
    "CI/CD": ("DevOps", None, ["ci/cd", "ci cd", "continuous integration", "continuous delivery", "continuous deployment"]),
    "Jenkins": ("DevOps", "ci-tool", ["jenkins"]),
    "GitHub Actions": ("DevOps", "ci-tool", ["github actions"]),
    "GitLab CI": ("DevOps", "ci-tool", ["gitlab ci", "gitlab-ci"]),
    "Git": ("Tools", None, ["git", "github", "gitlab", "bitbucket"]),
    "Linux": ("DevOps", None, ["linux", "unix", "ubuntu", "rhel"]),
    "Maven": ("Tools", "build-tool", ["maven"]),
    "Gradle": ("Tools", "build-tool", ["gradle"]),
    "Prometheus": ("DevOps", "observability", ["prometheus"]),
    "Grafana": ("DevOps", "observability", ["grafana"]),

    "JUnit": ("Testing", "unit-test", ["junit", "junit5", "mockito"]),
    "PyTest": ("Testing", "unit-test", ["pytest"]),
    "Jest": ("Testing", "unit-test", ["jest"]),
    "Selenium": ("Testing", None, ["selenium"]),
    "Unit Testing": ("Testing", None, ["unit testing", "unit tests", "tdd", "test driven development", "test-driven development"]),
    "Agile": ("Process", None, ["agile", "scrum", "kanban", "sprint planning"]),
    "Jira": ("Tools", None, ["jira"]),

    "Machine Learning": ("Data & AI", None, ["machine learning", "ml"]),
    "Deep Learning": ("Data & AI", None, ["deep learning", "neural networks"]),
    "NLP": ("Data & AI", None, ["nlp", "natural language processing"]),
    "Computer Vision": ("Data & AI", None, ["computer vision", "opencv"]),
    "LLMs": ("Data & AI", None, ["llm", "llms", "large language models", "generative ai", "genai", "rag", "prompt engineering"]),
    "TensorFlow": ("Data & AI", "dl-framework", ["tensorflow", "keras"]),
    "PyTorch": ("Data & AI", "dl-framework", ["pytorch", "torch"]),
    "scikit-learn": ("Data & AI", None, ["scikit-learn", "sklearn", "scikit learn"]),
    "Pandas": ("Data & AI", "dataframe", ["pandas"]),
    "NumPy": ("Data & AI", None, ["numpy"]),
    "Spark": ("Data Engineering", "big-data", ["spark", "apache spark", "pyspark"]),
    "Hadoop": ("Data Engineering", "big-data", ["hadoop", "hdfs", "hive"]),
    "Airflow": ("Data Engineering", None, ["airflow", "apache airflow"]),
    "ETL": ("Data Engineering", None, ["etl", "elt", "data pipelines", "data pipeline"]),
    "Statistics": ("Data & AI", None, ["statistics", "statistical analysis", "hypothesis testing", "a/b testing"]),
    "Tableau": ("Data & AI", "bi", ["tableau"]),
    "Power BI": ("Data & AI", "bi", ["power bi", "powerbi"]),
    "Excel": ("Tools", None, ["Excel", "ms excel", "advanced excel"]),
    "MLOps": ("Data & AI", None, ["mlops", "mlflow", "model deployment"]),

    "OAuth / JWT": ("Security", None, ["oauth", "oauth2", "jwt", "spring security", "openid connect"]),

    "Figma": ("Design", None, ["figma"]),
    "Storybook": ("Frontend", None, ["storybook"]),
    "Accessibility": ("Frontend", None, ["accessibility", "wcag", "a11y"]),
    "Web Performance": ("Frontend", None, ["web performance", "core web vitals", "lighthouse"]),
    "Zustand": ("Frontend", None, ["zustand"]),
    "Webpack / Vite": ("Frontend", None, ["webpack", "vite"]),
    "Cypress": ("Testing", "e2e-test", ["cypress"]),
    "Playwright": ("Testing", "e2e-test", ["playwright"]),

    "dbt": ("Data Engineering", None, ["dbt"]),
    "Snowflake": ("Data Engineering", "warehouse", ["snowflake"]),
    "BigQuery": ("Data Engineering", "warehouse", ["bigquery"]),
    "Redshift": ("Data Engineering", "warehouse", ["redshift"]),
    "Databricks": ("Data Engineering", None, ["databricks"]),
    "Kafka Streams / Flink": ("Data Engineering", None, ["flink", "kafka streams"]),
    "Looker": ("Data & AI", "bi", ["looker", "looker studio"]),
    "Data Visualization": ("Data & AI", None, ["data visualization", "data visualisation", "dashboards", "dashboarding"]),

    "Helm": ("DevOps", None, ["helm"]),
    "ArgoCD": ("DevOps", "gitops", ["argocd", "argo cd", "fluxcd"]),
    "OpenTelemetry": ("DevOps", "observability", ["opentelemetry", "otel"]),
    "Datadog": ("DevOps", "observability", ["datadog"]),
    "Networking": ("Fundamentals", None, ["networking", "tcp/ip", "dns", "load balancing"]),
    "Incident Management": ("DevOps", None, ["incident management", "incident response", "incident reviews",
                                            "on call", "on-call", "postmortems", "post-mortems"]),
    "Celery": ("Backend", None, ["celery"]),

    "Communication": ("Soft Skills", None, ["communication skills", "communication", "stakeholder management"]),
    "Leadership": ("Soft Skills", None, ["leadership", "mentoring", "mentored", "team lead", "led a team"]),
    "Problem Solving": ("Soft Skills", None, ["problem solving", "problem-solving", "analytical skills"]),
}

DESCRIPTIONS: dict[str, str] = {
    "Kafka": "event streaming platform, publishing and consuming messages between services",
    "RabbitMQ": "message broker and message queues for asynchronous processing",
    "Microservices": "independently deployable services, decomposing a monolith into small services",
    "REST APIs": "building HTTP web APIs and endpoints for clients",
    "GraphQL": "GraphQL query API schema and resolvers",
    "Docker": "packaging applications into containers",
    "Kubernetes": "container orchestration and deploying containers to clusters",
    "CI/CD": "automated build, test and deployment pipelines",
    "AWS": "Amazon cloud services infrastructure",
    "Terraform": "infrastructure as code provisioning of cloud resources",
    "Redis": "in-memory caching layer to reduce latency",
    "SQL": "writing SQL queries against relational databases",
    "PostgreSQL": "PostgreSQL relational database schema design and queries",
    "JUnit": "writing unit tests for Java code",
    "Unit Testing": "writing automated unit tests and test coverage",
    "Agile": "working in agile scrum teams with sprints",
    "System Design": "designing scalable distributed systems architecture",
    "Multithreading": "concurrent and multithreaded programming",
    "Machine Learning": "training predictive models on data",
    "Deep Learning": "training neural network models",
    "NLP": "natural language processing of text documents",
    "Statistics": "statistical analysis and hypothesis testing of experiments",
    "ETL": "building data pipelines that extract, transform and load data",
    "Spark": "distributed big data processing with Spark",
    "Prometheus": "metrics monitoring and alerting",
    "Grafana": "monitoring dashboards for metrics",
    "Leadership": "leading and mentoring a team of engineers",
    "Communication": "communicating with stakeholders and presenting findings",
    "Problem Solving": "solving complex technical problems and debugging issues",
    "Tableau": "building business intelligence dashboards and data visualizations",
    "Power BI": "building business intelligence dashboards and data visualizations",
}


IMPLIED_BY: dict[str, set[str]] = {
    "SQL": {"PostgreSQL", "MySQL", "Oracle DB", "SQL Server"},
    "Git": {"GitHub Actions", "GitLab CI"},
    "CI/CD": {"Jenkins", "GitHub Actions", "GitLab CI"},
    "Spring Framework": {"Spring Boot"},
    "Docker": {"Kubernetes"},
    "JavaScript": {"TypeScript", "React", "Angular", "Vue.js", "Node.js"},
    "Python": {"Django", "Flask", "FastAPI", "Pandas", "PyTorch", "scikit-learn"},
    "Machine Learning": {"scikit-learn", "Deep Learning", "PyTorch", "TensorFlow"},
    "Data Visualization": {"Tableau", "Power BI", "Looker"},
}


def semantic_query(skill: str) -> str:
    desc = DESCRIPTIONS.get(skill)
    return f"{skill}: {desc}" if desc else f"experience with {skill}"


CASE_SENSITIVE_ALIASES = {"C", "Go", "R", "REST", "Excel", "Spring"}

SOFT_SKILL_CATEGORY = "Soft Skills"


def _build():
    skills = {}
    for canonical, (category, family, aliases) in _RAW.items():
        all_aliases = list(dict.fromkeys([*aliases, canonical if canonical in CASE_SENSITIVE_ALIASES else canonical.lower()]))
        skills[canonical] = {"category": category, "family": family, "aliases": all_aliases}
    return skills


SKILLS: dict[str, dict] = _build()


def category_of(skill: str) -> str:
    return SKILLS.get(skill, {}).get("category", "Other")


def family_of(skill: str) -> str | None:
    return SKILLS.get(skill, {}).get("family")


def siblings(skill: str) -> set[str]:
    """Skills in the same substitute family (excluding the skill itself)."""
    fam = family_of(skill)
    if not fam:
        return set()
    return {s for s, meta in SKILLS.items() if meta["family"] == fam and s != skill}

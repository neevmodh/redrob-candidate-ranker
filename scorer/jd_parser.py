"""
scorer/jd_parser.py — Job Description parser and skill taxonomy

The JD is hardcoded (no file I/O during ranking — per spec constraints).
Role: Senior AI Engineer, Founding Team @ Redrob AI (Series A)
Location: Pune/Noida, India (Hybrid)
Experience: 5-9 years
"""

from __future__ import annotations
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Full JD text (hardcoded for offline operation)
# ---------------------------------------------------------------------------
JD_TEXT = """
Senior AI Engineer — Founding Team at Redrob AI (Series A, Pune/Noida, Hybrid).
5-9 years experience. Must-have: production embeddings-based retrieval systems
(sentence-transformers, BGE, E5, OpenAI embeddings), vector databases (Pinecone,
Weaviate, Qdrant, Milvus, FAISS, OpenSearch, Elasticsearch), strong Python,
evaluation frameworks for ranking systems (NDCG, MRR, MAP, A/B testing).
Nice-to-have: LLM fine-tuning (LoRA, QLoRA, PEFT), learning-to-rank (XGBoost or
neural), HR-tech or marketplace products, distributed systems, open-source AI/ML.
Seeking someone who shipped end-to-end ranking, search, or recommendation system
at product companies. Hybrid retrieval, embedding drift, index refresh, re-ranking,
recommendation systems, NLP, information retrieval, RAG, vector search.
Disqualifiers: entire career at TCS/Infosys/Wipro/Accenture/Cognizant/Capgemini,
pure research without production deployment, primary CV/speech/robotics without NLP,
title-chasers switching every 1.5 years, only LangChain wrappers without pre-LLM ML.
"""


# ---------------------------------------------------------------------------
# Skill alias map — normalise variant spellings to a canonical group key
# ---------------------------------------------------------------------------
SKILL_ALIASES: dict[str, str] = {
    # Vector DBs / Search infrastructure
    "faiss": "vector_db",
    "pinecone": "vector_db",
    "milvus": "vector_db",
    "qdrant": "vector_db",
    "weaviate": "vector_db",
    "opensearch": "vector_db",
    "elasticsearch": "vector_db",
    "chroma": "vector_db",
    "pgvector": "vector_db",
    "annoy": "vector_db",
    "scann": "vector_db",
    "vespa": "vector_db",

    # Embeddings / Retrieval
    "sentence-transformers": "embeddings",
    "sentence transformers": "embeddings",
    "bge": "embeddings",
    "e5": "embeddings",
    "embedding": "embeddings",
    "embeddings": "embeddings",
    "dense retrieval": "embeddings",
    "bi-encoder": "embeddings",
    "cross-encoder": "embeddings",
    "semantic search": "embeddings",
    "semantic similarity": "embeddings",
    "openai embeddings": "embeddings",
    "ada": "embeddings",

    # Ranking / Information Retrieval
    "ranking": "ranking",
    "ranker": "ranking",
    "information retrieval": "ranking",
    "ir": "ranking",
    "bm25": "ranking",
    "tfidf": "ranking",
    "tf-idf": "ranking",
    "hybrid search": "ranking",
    "hybrid retrieval": "ranking",
    "learning to rank": "learning_to_rank",
    "learning-to-rank": "learning_to_rank",
    "ltr": "learning_to_rank",
    "lambdamart": "learning_to_rank",
    "xgboost": "learning_to_rank",
    "lightgbm": "learning_to_rank",

    # Evaluation
    "ndcg": "eval_framework",
    "mrr": "eval_framework",
    "map": "eval_framework",
    "a/b testing": "eval_framework",
    "a/b test": "eval_framework",
    "ab testing": "eval_framework",
    "offline evaluation": "eval_framework",
    "online evaluation": "eval_framework",
    "recall@k": "eval_framework",
    "precision@k": "eval_framework",

    # LLM / Fine-tuning
    "lora": "llm_finetuning",
    "qlora": "llm_finetuning",
    "peft": "llm_finetuning",
    "fine-tuning llms": "llm_finetuning",
    "fine-tuning": "llm_finetuning",
    "finetuning": "llm_finetuning",
    "instruction tuning": "llm_finetuning",
    "rlhf": "llm_finetuning",
    "dpo": "llm_finetuning",
    "sft": "llm_finetuning",

    # NLP
    "nlp": "nlp",
    "natural language processing": "nlp",
    "text classification": "nlp",
    "named entity recognition": "nlp",
    "ner": "nlp",
    "text mining": "nlp",
    "sentiment analysis": "nlp",
    "question answering": "nlp",
    "summarisation": "nlp",
    "summarization": "nlp",
    "transformers": "nlp",
    "bert": "nlp",
    "roberta": "nlp",
    "gpt": "nlp",
    "llm": "nlp",
    "large language model": "nlp",
    "rag": "nlp",
    "retrieval augmented generation": "nlp",

    # Recommendation Systems
    "recommendation": "recsys",
    "recommendation systems": "recsys",
    "recommender systems": "recsys",
    "collaborative filtering": "recsys",
    "matrix factorization": "recsys",
    "two-tower": "recsys",

    # ML Engineering / MLOps
    "mlflow": "mlops",
    "mlops": "mlops",
    "kubeflow": "mlops",
    "model serving": "mlops",
    "triton": "mlops",
    "torchserve": "mlops",
    "bentoml": "mlops",
    "ray serve": "mlops",
    "feature store": "mlops",
    "feature engineering": "mlops",
    "weights & biases": "mlops",
    "wandb": "mlops",

    # ML Core
    "machine learning": "ml_core",
    "ml": "ml_core",
    "deep learning": "ml_core",
    "neural networks": "ml_core",
    "pytorch": "ml_core",
    "tensorflow": "ml_core",
    "scikit-learn": "ml_core",
    "sklearn": "ml_core",
    "statistical modeling": "ml_core",
    "statistical modelling": "ml_core",

    # Data / Engineering
    "python": "python",
    "sql": "data_eng",
    "spark": "data_eng",
    "kafka": "data_eng",
    "airflow": "data_eng",
    "databricks": "data_eng",

    # Search infra
    "search": "search",
    "search engineer": "search",
    "search infrastructure": "search",
    "solr": "search",
    "lucene": "search",
    "vector search": "search",
}

# Canonical group → human-readable label for reasoning
GROUP_LABELS: dict[str, str] = {
    "vector_db": "vector DB/search infra",
    "embeddings": "embedding/retrieval",
    "ranking": "ranking/IR",
    "learning_to_rank": "learning-to-rank",
    "eval_framework": "evaluation frameworks",
    "llm_finetuning": "LLM fine-tuning",
    "nlp": "NLP/LLM",
    "recsys": "recommendation systems",
    "mlops": "MLOps",
    "ml_core": "core ML",
    "python": "Python",
    "data_eng": "data engineering",
    "search": "search engineering",
}


def normalise_skill(name: str) -> str:
    """Return canonical group key for a skill name, or original lowercased."""
    return SKILL_ALIASES.get(name.lower().strip(), name.lower().strip())


# ---------------------------------------------------------------------------
# JobDescription dataclass
# ---------------------------------------------------------------------------

@dataclass
class JobDescription:
    title: str = "Senior AI Engineer"
    company: str = "Redrob AI"
    location: str = "Pune/Noida, India"
    min_years: int = 5
    max_years: int = 9
    ideal_years: int = 7  # midpoint

    # Skills: stored as canonical group keys for fast matching
    must_have_skills: list[str] = field(default_factory=list)
    nice_to_have_skills: list[str] = field(default_factory=list)

    # Raw skill name variants (for display/reasoning)
    must_have_raw: list[str] = field(default_factory=list)
    nice_to_have_raw: list[str] = field(default_factory=list)

    # Titles that are a direct match for this role
    ideal_titles: list[str] = field(default_factory=list)
    ideal_title_keywords: list[str] = field(default_factory=list)

    # Disqualifier signals
    disqualifier_companies: list[str] = field(default_factory=list)
    disqualifier_company_keywords: list[str] = field(default_factory=list)

    # Location preferences
    preferred_locations: list[str] = field(default_factory=list)
    preferred_notice_days: int = 30

    # Career description keywords (for semantic matching in descriptions)
    career_keywords: list[str] = field(default_factory=list)
    production_keywords: list[str] = field(default_factory=list)
    anti_pattern_keywords: list[str] = field(default_factory=list)


def get_job_description() -> JobDescription:
    """
    Build and return the structured JobDescription for the Redrob Senior AI
    Engineer role. Hardcoded — no file I/O.
    """
    jd = JobDescription()

    # ------------------------------------------------------------------
    # Must-have skills (canonical group keys)
    # ------------------------------------------------------------------
    jd.must_have_skills = [
        "embeddings",       # sentence-transformers, BGE, E5, OpenAI embeddings
        "vector_db",        # Pinecone, Milvus, FAISS, Qdrant, Weaviate
        "ranking",          # BM25, hybrid search, IR
        "eval_framework",   # NDCG, MRR, MAP, A/B testing
        "python",           # Strong Python
        "nlp",              # NLP / LLM exposure
        "ml_core",          # Core ML fundamentals
        "search",           # Search engineering
    ]

    jd.must_have_raw = [
        "embeddings", "FAISS/Pinecone/Milvus", "ranking/BM25",
        "NDCG/MRR/A-B testing", "Python", "NLP/LLMs", "ML", "search infra",
    ]

    # ------------------------------------------------------------------
    # Nice-to-have skills
    # ------------------------------------------------------------------
    jd.nice_to_have_skills = [
        "llm_finetuning",    # LoRA, QLoRA, PEFT
        "learning_to_rank",  # XGBoost LTR, neural LTR
        "recsys",            # Recommendation systems
        "mlops",             # MLflow, model serving, feature stores
        "data_eng",          # Spark, Kafka, Airflow (infra background)
    ]

    jd.nice_to_have_raw = [
        "LoRA/QLoRA", "learning-to-rank", "recommendation systems",
        "MLOps/MLflow", "data engineering",
    ]

    # ------------------------------------------------------------------
    # Ideal job titles (exact or partial match)
    # ------------------------------------------------------------------
    jd.ideal_titles = [
        "Machine Learning Engineer",
        "ML Engineer",
        "Senior Machine Learning Engineer",
        "Staff Machine Learning Engineer",
        "Applied Scientist",
        "Senior Applied Scientist",
        "NLP Engineer",
        "Senior NLP Engineer",
        "Search Engineer",
        "Applied ML Engineer",
        "Recommendation Systems Engineer",
        "AI Engineer",
        "Senior AI Engineer",
        "Lead AI Engineer",
        "Data Scientist",
        "Senior Data Scientist",
    ]

    # Keywords extracted from ideal titles — for partial matching
    jd.ideal_title_keywords = [
        "machine learning", "ml engineer", "applied scientist",
        "nlp engineer", "nlp", "search engineer", "applied ml",
        "recommendation", "ai engineer", "data scientist",
        "retrieval", "ranking", "research scientist",
    ]

    # ------------------------------------------------------------------
    # Disqualifier companies — entire career at these = bad fit signal
    # ------------------------------------------------------------------
    jd.disqualifier_companies = [
        "TCS", "Tata Consultancy Services",
        "Infosys",
        "Wipro",
        "Accenture",
        "Cognizant",
        "Capgemini",
        "HCL Technologies", "HCL",
        "Tech Mahindra",
        "Mphasis",
        "Hexaware",
        "Mindtree",
        "NIIT Technologies",
        "L&T Infotech", "LTI", "LTIMindtree",
    ]

    jd.disqualifier_company_keywords = [
        "tcs", "infosys", "wipro", "accenture", "cognizant",
        "capgemini", "hcl", "tech mahindra", "mphasis", "hexaware",
        "mindtree", "niit", "lti", "ltimindtree",
    ]

    # ------------------------------------------------------------------
    # Preferred locations
    # ------------------------------------------------------------------
    jd.preferred_locations = [
        "Pune", "Noida", "Delhi", "Gurugram", "Gurgaon",
        "Mumbai", "Hyderabad", "Bangalore", "Bengaluru",
    ]

    jd.preferred_notice_days = 30  # JD explicitly says sub-30 preferred

    # ------------------------------------------------------------------
    # Career description keywords (for semantic match in role descriptions)
    # ------------------------------------------------------------------
    jd.career_keywords = [
        "embedding", "embeddings", "retrieval", "ranking", "search",
        "vector", "faiss", "pinecone", "milvus", "qdrant", "weaviate",
        "recommendation", "nlp", "language model", "llm", "transformer",
        "bert", "bm25", "hybrid search", "semantic search",
        "information retrieval", "lora", "qlora", "fine-tuning", "rag",
        "reranking", "re-ranking", "learning to rank", "ndcg", "mrr",
        "a/b test", "relevance", "query", "index", "inverted index",
        "dense retrieval", "sparse retrieval", "two-tower", "bi-encoder",
        "cross-encoder", "candidate retrieval", "feature store",
        "model serving", "inference", "latency", "throughput",
    ]

    # Strong positive signal: production mindset keywords
    jd.production_keywords = [
        "production", "deployed", "deployment", "shipped", "scaled",
        "real users", "serving", "latency", "throughput", "a/b",
        "million", "billion", "at scale", "prod", "live",
        "online", "inference", "api", "microservice",
    ]

    # Anti-pattern keywords in descriptions (reduces score)
    jd.anti_pattern_keywords = [
        "langchain tutorial", "demo", "toy project", "side project",
        "kaggle only", "academic", "research only", "no production",
        "consulting", "slide", "powerpoint", "excel", "business analyst",
    ]

    return jd

# Kintsugi Agent

Kintsugi Agent is a Python-based AI assistant for cloud operations and incident troubleshooting. It is designed to help teams ground responses in internal runbooks and operational knowledge, retrieve relevant context from a vector database, and optionally augment that context with live web search.

The project combines:

- LangChain-based orchestration
- Hugging Face embeddings
- Pinecone vector storage for semantic retrieval
- document ingestion for operational runbooks and support docs
- environment-driven configuration for cloud and tool integrations

This repository is structured as the foundation for a CloudOps or incident-response agent, with ready-to-use ingestion and retrieval utilities and a configuration layer for integrating LLM, search, and vector database providers.

## Why this project exists

Operational teams often have useful troubleshooting material spread across:

- incident runbooks
- architecture notes
- AWS / Kubernetes / database troubleshooting docs
- historical support documents

Kintsugi Agent helps turn that knowledge into a searchable, retrievable knowledge base so an AI agent can answer questions like:

- Why is my Kubernetes pod CrashLoopBackOff?
- Why are Postgres RDS connections exhausted?
- What are the common causes of ALB 504 errors?
- What should I check when Redis memory pressure leads to latency spikes?

The included `documents/` folder contains runbook-style examples that align with those problem areas.

## Architecture overview

The current project is centered around three main responsibilities:

1. Configuration and environment setup
   - `src/config.py` loads app settings from `.env`
   - centralized configuration for Pinecone, OpenAI, Hugging Face, Tavily, LangSmith, and app runtime

2. Document ingestion and chunking
   - `src/ingestion.py` loads supported file types (`.pdf`, `.txt`, `.md`, `.docx`)
   - splits documents into chunks for embedding
   - writes them to a Pinecone vector index with deterministic IDs

3. Vector retrieval and search
   - `src/vector_store.py` creates and configures the embedding model and Pinecone vector store
   - provides a retriever that can return the most relevant context for a user query

## Repository structure

```text
Kintsugi-agent/
├── .env.example                  # Example environment configuration
├── .gitignore                    # Git ignore rules
├── documents/                    # Runbook / troubleshooting documents
│   ├── RB-001-k8s-pod-crashloop-oomkilled.md
│   ├── RB-002-postgres-rds-connection-exhaustion.md
│   ├── RB-003-aws-alb-ingress-504-gateway-timeout.md
│   └── RB-004-redis-cache-memory-eviction-latency.md
├── requirements.txt              # Python dependencies
├── src/
│   ├── __init__.py
│   ├── config.py                 # Settings and environment config
│   ├── ingestion.py              # Document ingestion and chunking
│   ├── test.py                   # Minimal config smoke test
│   └── vector_store.py           # Embeddings and Pinecone integration
└── README.md                     # Project documentation
```

## Features

- Supports ingestion of Markdown, text, PDF, and DOCX documents
- Uses recursive chunking with overlap for retrieval quality
- Creates stable vector IDs to make document re-ingestion idempotent
- Uses Hugging Face sentence-transformers embeddings by default
- Integrates with Pinecone Serverless indexes
- Designed for retrieval-augmented generation (RAG) style workflows
- Supports LangSmith tracing and Tavily web search hooks
- Environment-based configuration for production deployment

## Technology stack

- Python 3
- FastAPI / Uvicorn
- LangChain and LangGraph
- Hugging Face Embeddings
- Pinecone vector database
- Tavily web search
- SQLite database support (via `database_path` in settings)
- Pydantic + Pydantic Settings

## Prerequisites

Before running the project, make sure you have:

- Python 3.10+ recommended
- an active Pinecone account and API key
- an OpenAI API key (if using OpenAI-backed LLM workflows)
- a Hugging Face token if needed for gated models
- optionally a Tavily API key for web search
- optionally a LangSmith API key if you want tracing and evaluation

## Installation

Clone the repository:

```bash
git clone https://github.com/SougataXdev/Kintsugi-agent.git
cd Kintsugi-agent
```

Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# On Windows: .venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Environment configuration

Copy the sample environment file and update it with your credentials:

```bash
cp .env.example .env
```

At minimum, set values similar to the following:

```dotenv
PINECONE_API_KEY=your_pinecone_api_key_here
PINECONE_INDEX_NAME=cloudops-agent
PINECONE_CLOUD=aws
PINECONE_REGION=us-east-1
OPENAI_API_KEY=your_openai_api_key_here
TAVILY_API_KEY=your_tavily_api_key_here
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_api_key_here
LANGCHAIN_PROJECT=cloudops-agent
```

The project also supports these optional values:

```dotenv
HUGGINGFACE_API_KEY=your_huggingface_api_key_here
TOP_K=5
MAX_SUPPORT_RETRIES=2
MAX_RETRIEVAL_REWRITES=2
MAX_WEB_REWRITES=2
DATABASE_PATH=data/audit.db
```

Note: `src/config.py` loads `.env` automatically from the repository root.

## Running the project

This repository currently focuses on the reusable agent components rather than a single application entrypoint. In other words, the project is built around configuration, ingestion, and retrieval logic that can be imported by a service or application layer.

You can validate the configuration by running:

```bash
python src/test.py
```

This just prints the configured LangSmith key value or confirms the app loads without crashing.

## Ingesting documents into the knowledge base

The ingestion utilities are designed to load runbooks and troubleshooting docs into Pinecone. Example:

```python
from pathlib import Path
from src.ingestion import ingest_directory

result = ingest_directory("documents")
print(result)
```

This processes every supported file in the directory and adds chunked content to the configured vector store.

You can also ingest a single file:

```python
from src.ingestion import ingest_file

count = ingest_file("documents/RB-001-k8s-pod-crashloop-oomkilled.md")
print(f"Added {count} chunks")
```

## Using the retriever

After ingestion, you can query the vector store for relevant context:

```python
from src.vector_store import get_retriever

retriever = get_retriever()
results = retriever.invoke("What should I check when a Kubernetes pod is OOMKilled?")

for doc in results:
    print(doc.page_content[:500])
```

This pattern is the foundation for building a question-answering agent over your internal operational knowledge.

## Document set included in this repo

The repository includes runbook documents covering common platform issues:

- `RB-001-k8s-pod-crashloop-oomkilled.md`
  - Kubernetes pod CrashLoopBackOff / OOMKilled analysis
- `RB-002-postgres-rds-connection-exhaustion.md`
  - RDS connection exhaustion troubleshooting
- `RB-003-aws-alb-ingress-504-gateway-timeout.md`
  - ALB ingress timeout and 504 investigation
- `RB-004-redis-cache-memory-eviction-latency.md`
  - Redis memory pressure and latency troubleshooting

These docs are excellent examples for testing ingestion and retrieval workflows.

## Recommended usage patterns

This project is especially useful when building:

- an internal SRE troubleshooting assistant
- a cloud operations copilot
- a runbook retrieval agent for incident response
- a RAG-powered knowledge assistant for platform teams

Typical flow:

1. ingest runbooks and support docs
2. embed them using a sentence-transformers model
3. store embeddings in Pinecone
4. retrieve the most relevant text for a user query
5. pass that context into an LLM for grounded answers
6. optionally enrich with Tavily search or other live web sources

## Security and configuration notes

- Store secrets in `.env` and keep it out of source control
- Do not commit production API keys or tokens
- Prefer environment variables over hard-coded configuration
- If you change embedding models, ensure Pinecone index dimensions match the model

## Troubleshooting

If ingestion or retrieval fails:

- verify your Pinecone API key and index name
- confirm the embedding dimension matches the selected model
- make sure the `.env` file is loaded correctly
- ensure your document directory contains supported file types
- confirm that Pinecone has enough quota and the index exists

## Future improvements

Potential next steps for this project include:

- add a FastAPI app entrypoint for agent HTTP endpoints
- add agent orchestration around tool-calling and retrieval
- build a web UI for querying the knowledge base
- add automated tests for ingestion and retrieval
- integrate a richer incident triage workflow
- support additional external knowledge sources beyond Pinecone and Tavily

## License

This repository does not currently include a license file. If you plan to share or distribute the project publicly, consider adding an explicit license such as MIT or Apache-2.0.

## Contributing

Contributions are welcome. A good starting point is to:

1. fork the repository
2. create a feature branch
3. improve the ingestion pipeline or agent workflow
4. add tests and documentation
5. submit a pull request

## Summary

Kintsugi Agent is a practical foundation for building a retrieval-augmented operations assistant focused on runbooks, troubleshooting knowledge, and incident response. It is well-suited for teams that want to give LLMs access to structured operational knowledge and keep answers grounded in internal documentation.

If you want, this README can also be expanded with:

- a diagram of the retrieval pipeline
- a section for local API usage
- an optional Docker setup
- a more opinionated “how the agent works” walkthrough

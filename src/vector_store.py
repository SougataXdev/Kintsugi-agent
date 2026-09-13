from src.config import get_settings
from pinecone import Pinecone, ServerlessSpec
from functools import lru_cache
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_pinecone import PineconeVectorStore
from src.config import settings

# Build model kwargs conditionally based on HUGGINGFACE_API_KEY
model_kwargs = {}
if settings.huggingface_api_key and settings.huggingface_api_key != "your_huggingface_api_key_here":
    model_kwargs["token"] = settings.huggingface_api_key

embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2",
    model_kwargs=model_kwargs,
    encode_kwargs={"normalize_embeddings": True},
)


def get_embeddings() -> HuggingFaceEmbeddings:
    return embeddings


def get_pinecone_client():
    s = get_settings()
    if not s.pinecone_api_key:
        raise RuntimeError("PINECONE_API_KEY is not configured")
    return Pinecone(api_key=s.pinecone_api_key)



def ensure_index():
    """Create the Pinecone index if needed and verify embedding dimension compatibility."""
    s = get_settings()
    pc = get_pinecone_client()
    existing = {x.name for x in pc.list_indexes()}

    if s.pinecone_index_name not in existing:
        pc.create_index(
            name=s.pinecone_index_name,
            dimension=s.embedding_dimension,
            metric="cosine",
            spec=ServerlessSpec(cloud=s.pinecone_cloud, region=s.pinecone_region),
        )
    else:
        desc = pc.describe_index(s.pinecone_index_name)
        existing_dimension = getattr(desc, "dimension", None)
        if existing_dimension is None and isinstance(desc, dict):
            existing_dimension = desc.get("dimension")
        if existing_dimension and int(existing_dimension) != s.embedding_dimension:
            raise RuntimeError(
                f"Pinecone index '{s.pinecone_index_name}' has dimension {existing_dimension}, "
                f"but {s.embedding_model} is configured for {s.embedding_dimension}. "
                "Use a new index name or recreate the index with the correct dimension."
            )

    return pc.Index(s.pinecone_index_name)



def get_vector_store():
    s = get_settings()
    index = ensure_index()
    return PineconeVectorStore(
        index=index,
        embedding=embeddings,
        namespace=s.pinecone_namespace,
    )




def get_retriever():
    s = get_settings()
    return get_vector_store().as_retriever(search_kwargs={"k": s.top_k})

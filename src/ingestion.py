from src.vector_store import get_vector_store
from pathlib import Path
from typing import Dict, List, Union
from hashlib import sha256
from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from docx import Document as DocxDocument
from src.config import get_settings


SUPPORTED = {".pdf", ".txt", ".md", ".docx"}





def _load_docx(path: Path) -> List[Document]:
    doc = DocxDocument(path)
    text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    return [Document(page_content=text, metadata={"source": str(path), "title": path.name})]


def load_file(path: Union[Path, str]) -> List[Document]:
    """Load a document from a supported file format (.pdf, .txt, .md, .docx).

    Args:
        path: Path object or string path to the file.

    Returns:
        A list of LangChain Document objects with consistent metadata.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file format is unsupported.
    """
    file_path = Path(path).resolve()
    if not file_path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")

    suffix = file_path.suffix.lower()
    if suffix not in SUPPORTED:
        raise ValueError(
            f"Unsupported file format '{suffix}'. Supported formats are: {', '.join(sorted(SUPPORTED))}"
        )

    if suffix == ".pdf":
        loader = PyPDFLoader(str(file_path))
        docs = loader.load()
    elif suffix in {".txt", ".md"}:
        loader = TextLoader(str(file_path), encoding="utf-8")
        docs = loader.load()
    elif suffix == ".docx":
        docs = _load_docx(file_path)
    else:
        docs = []

    # Standardize metadata across loaders
    for doc in docs:
        doc.metadata.setdefault("source", str(file_path))
        doc.metadata.setdefault("title", file_path.name)
        doc.metadata.setdefault("file_type", suffix)

    return docs


def _stable_chunk_id(
    source: Union[Document, Path, str],
    chunk_index: int,
    content: str = "",
) -> str:
    """Generate a deterministic and stable SHA-256 ID for a document chunk.

    Ensures idempotent upserts into vector stores (e.g. Pinecone).

    Args:
        source: Document instance, file path, or source identifier string.
        chunk_index: Index of the chunk within the document sequence.
        content: Optional chunk content string (automatically extracted if source is a Document).

    Returns:
        A deterministic 64-character SHA-256 hexadecimal string.
    """
    if isinstance(source, Document):
        doc_source = source.metadata.get("source", source.metadata.get("title", "document"))
        doc_content = content or source.page_content
    else:
        doc_source = str(source)
        doc_content = content

    raw_key = f"{doc_source}:{chunk_index}:{doc_content}"
    return sha256(raw_key.encode("utf-8")).hexdigest()


def ingest_file(path: Union[Path, str]) -> int:
    file_path = Path(path).resolve()
    docs = load_file(file_path)
    if not docs:
        return 0

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=160,
        separators=["\n\n", "\n", " ", "", ". "],
    )

    chunks = splitter.split_documents(docs)
    if not chunks:
        return 0

    index_name = get_settings().pinecone_index_name
    for i, chunk in enumerate(chunks):
        chunk.metadata["chunk_index"] = i
        chunk.metadata["knowledge_base"] = index_name

    ids = [_stable_chunk_id(chunk, i) for i, chunk in enumerate(chunks)]
    get_vector_store().add_documents(chunks, ids=ids)
    return len(chunks)


def ingest_directory(
    directory_path: Union[Path, str],
    glob_pattern: str = "**/*",
    recursive: bool = True,
) -> Dict[str, Union[int, List[str]]]:
    """Recursively ingests all supported files from a directory into the vector store.

    Args:
        directory_path: Path to the directory containing documents.
        glob_pattern: Glob pattern for matching files (defaults to '**/*').
        recursive: Whether to scan directory recursively.

    Returns:
        Dictionary with ingestion statistics (total_files, successful_files, total_chunks, failed_files).
    """
    dir_path = Path(directory_path).resolve()
    if not dir_path.is_dir():
        raise NotADirectoryError(f"Directory not found: {dir_path}")

    files = [
        p for p in (dir_path.rglob(glob_pattern.lstrip("/")) if recursive else dir_path.glob(glob_pattern))
        if p.is_file() and p.suffix.lower() in SUPPORTED
    ]

    total_chunks = 0
    successful_files = 0
    failed_files: List[str] = []

    for file_path in files:
        try:
            count = ingest_file(file_path)
            total_chunks += count
            successful_files += 1
        except Exception as exc:
            failed_files.append(f"{file_path.name}: {exc}")

    return {
        "total_files": len(files),
        "successful_files": successful_files,
        "total_chunks": total_chunks,
        "failed_files": failed_files,
    }


def namespace() -> str:
    return get_settings().pinecone_index_name
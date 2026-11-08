"""
vector_store.py — ChromaDB Vector Store Management
====================================================
This module handles all interactions with ChromaDB — the local vector database
that powers the RAG (Retrieval-Augmented Generation) step of the pipeline.

How RAG works here:
  1. We convert each per-video profile (text) into a high-dimensional embedding
     vector using a local sentence-transformer model.
  2. These vectors + original texts are stored in ChromaDB on disk.
  3. At query time, we embed the query and retrieve documents whose vectors
     are closest (most semantically similar) to the query vector.
  4. Those retrieved documents become the "context" fed to the LLM —
     this is Retrieval-Augmented Generation.

Why ChromaDB?
  - Runs entirely locally (no server, no Docker, no cloud API needed).
  - Persists data between runs — so you can re-run main.py without re-ingesting.
  - Clean Python API with native LangChain integration.
  - Lightweight enough for a laptop.

Why all-MiniLM-L6-v2?
  - Free, open-source, runs on CPU.
  - 384-dimensional vectors — compact but effective for semantic similarity.
  - ~90 MB, cached after first download.
"""

import json
from typing import Any

from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.retrievers import BaseRetriever
from rich.console import Console

console = Console()


def initialize_vector_store(persist_dir: str, collection_name: str) -> Chroma:
    """
    Create or load a ChromaDB-backed vector store with HuggingFace embeddings.

    If persist_dir already contains data from a previous run, this function
    loads that existing collection (no re-ingestion needed). Otherwise, it
    creates a fresh empty collection.

    NOTE: On the very first call, HuggingFace downloads 'all-MiniLM-L6-v2'
    (~90 MB) to ~/.cache/huggingface/. All subsequent calls load from cache.

    Args:
        persist_dir:     Path where ChromaDB stores its SQLite database.
        collection_name: Name of the ChromaDB collection (like a table name).

    Returns:
        A LangChain Chroma instance with .add_texts() and .as_retriever().

    Raises:
        RuntimeError: If ChromaDB cannot initialise (permissions issue, etc.)
    """
    console.print(
        "\n  [yellow]⚙ Loading embedding model...[/yellow] "
        "(first run downloads ~90MB all-MiniLM-L6-v2, then cached)"
    )

    # ── HuggingFace Embeddings ────────────────────────────────────────────────
    # model_kwargs={"device": "cpu"} explicitly runs on CPU — avoids CUDA
    # errors on machines without a GPU and keeps setup simple for a POC.
    #
    # encode_kwargs={"normalize_embeddings": True} normalises vectors to unit
    # length. This makes cosine similarity equivalent to dot product and
    # generally improves retrieval quality.
    embeddings = HuggingFaceEmbeddings(
        model_name="all-MiniLM-L6-v2",
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
    console.print("  [green]✓ Embedding model ready[/green]")

    # ── ChromaDB Vector Store ─────────────────────────────────────────────────
    # LangChain's Chroma wrapper transparently handles both creating a new
    # collection and loading an existing one based on persist_directory.
    console.print(
        f"  [cyan]📦 Opening ChromaDB:[/cyan] collection='{collection_name}' "
        f"at '{persist_dir}'"
    )

    vector_store = Chroma(
        collection_name=collection_name,
        embedding_function=embeddings,
        persist_directory=persist_dir,
    )

    # Report how many documents are already stored — useful on restarts
    existing_count = vector_store._collection.count()
    if existing_count > 0:
        console.print(
            f"  [green]✓ Loaded existing collection[/green] "
            f"({existing_count} document(s) already stored)"
        )
    else:
        console.print("  [green]✓ Created new empty collection[/green]")

    return vector_store


def _profile_to_document_text(profile: dict[str, Any], video_index: int) -> str:
    """
    Convert a per-video profile dict into a formatted text document for embedding.

    This text is what gets embedded and stored in ChromaDB. The retrieval
    quality depends heavily on how well this text captures the profile's
    semantics.

    We write it as prose-like structured text rather than raw JSON because
    sentence-transformer models are trained on natural language and produce
    better semantic representations for prose than for JSON syntax.

    Args:
        profile:     Dict matching the per-video profile schema.
        video_index: 1-based index used for labelling in the document text.

    Returns:
        A formatted multi-line string representing the profile.
    """
    topic = profile.get("topic", "Unknown")
    hook_text = profile.get("hook_text", "")
    hook_type = profile.get("hook_type", "Unknown")
    structure = profile.get("structure", "Unknown")
    tone = profile.get("tone", "Unknown")
    pacing = profile.get("pacing", "Unknown")
    key_phrases = profile.get("key_phrases", [])
    summary = profile.get("transcript_summary", "")
    url = profile.get("video_url", "")

    # Format key_phrases as a readable quoted comma-separated string
    phrases_str = (
        ", ".join(f'"{p}"' for p in key_phrases) if key_phrases else "none"
    )

    return (
        f"Video {video_index}: {topic}\n"
        f"URL: {url}\n"
        f"Hook: {hook_text}\n"
        f"Hook Type: {hook_type}\n"
        f"Structure: {structure}\n"
        f"Tone: {tone}\n"
        f"Pacing: {pacing}\n"
        f"Key Phrases: {phrases_str}\n"
        f"Summary: {summary}"
    )


def store_video_profile(
    vector_store: Chroma,
    profile: dict[str, Any],
    video_index: int,
    transcript: str = "",
    language: str = "",
) -> None:
    """
    Store a per-video profile as a vector-embedded document in ChromaDB.

    ChromaDB stores three things per document:
      1. The raw text (for retrieval and display to the LLM).
      2. The embedding vector (for similarity search).
      3. Metadata dict (for filtering/display — NOT used in similarity search).

    The raw Whisper transcript is kept in metadata so the Scripting Agent
    can show the LLM the creator's real words (few-shot examples) and
    measure their style (sentence length, questions, "you"-address).

    Args:
        vector_store: Chroma instance from initialize_vector_store().
        profile:      Per-video profile dict from extract_video_profile().
        video_index:  1-based index used as the document ID and in metadata.
        transcript:   Raw transcript text for this video.
        language:     Spoken language Whisper detected (e.g. "en", "hi").
    """
    # Convert the profile dict to human-readable text for embedding.
    document_text = _profile_to_document_text(profile, video_index)

    # Metadata is stored alongside but NOT embedded — useful for filtering
    # and for surfacing additional context in retrieval results.
    metadata = {
        "video_index": video_index,
        "video_url": profile.get("video_url", ""),
        "topic": profile.get("topic", "Unknown"),
        "tone": profile.get("tone", "Unknown"),
        "pacing": profile.get("pacing", "Unknown"),
        "hook_type": profile.get("hook_type", "Unknown"),
        "hook_text": profile.get("hook_text", ""),
        "key_phrases": json.dumps(profile.get("key_phrases", []), ensure_ascii=False),
        "transcript": transcript,
        "language": language,
    }

    # Use a deterministic document ID so that re-running the pipeline
    # OVERWRITES existing documents instead of creating duplicates.
    # This is important for iterative development — you can re-run main.py
    # without accumulating stale data in ChromaDB.
    doc_id = f"video_{video_index}"

    # LangChain's add_texts() handles embedding + storage in one call.
    vector_store.add_texts(
        texts=[document_text],
        metadatas=[metadata],
        ids=[doc_id],
    )

    console.print(
        f"  [green]✓ Stored in ChromaDB:[/green] "
        f"'{profile.get('topic', 'Unknown')}' (id: {doc_id})"
    )


def get_retriever(vector_store: Chroma, k: int = 3) -> BaseRetriever:
    """
    Create and return a retriever that fetches the top-k most relevant documents.

    A retriever is a LangChain abstraction over the vector store's similarity
    search. Given a query string, it embeds the query and returns the k
    documents with the closest embedding vectors.

    For our POC with 3 videos, k=3 returns all documents — giving the LLM
    full context for building the master creator profile. In a production
    system with hundreds of videos, you'd tune k to balance context window
    size against coverage.

    Args:
        vector_store: Initialised Chroma instance.
        k:            Number of top documents to retrieve per query.

    Returns:
        A BaseRetriever callable with .invoke("query string") that returns
        a list of LangChain Document objects.
    """
    # search_type="similarity" uses cosine similarity (default for normalised
    # embeddings). Alternative "mmr" gives more diverse results — overkill
    # for 3 documents in our POC.
    retriever = vector_store.as_retriever(
        search_type="similarity",
        search_kwargs={"k": k},
    )

    console.print(
        f"  [green]✓ Retriever configured[/green] "
        f"(fetches top-{k} most relevant documents per query)"
    )
    return retriever

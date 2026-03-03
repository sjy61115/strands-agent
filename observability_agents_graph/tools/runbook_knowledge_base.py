import chromadb
from pathlib import Path

RUNBOOK_DIR = Path(__file__).resolve().parent.parent / "runbooks"


class RunbookKnowledgeBase:
    """
    로컬 런북 문서를 ChromaDB 벡터 DB에 인덱싱하고 검색하는 Knowledge Base.
    AWS 아키텍처의 S3(Run-Book) + OpenSearch Serverless(Vector DB) + Bedrock Knowledge Base를
    로컬에서 대체한다.
    """

    def __init__(self, runbook_dir: Path | None = None):
        self._runbook_dir = runbook_dir or RUNBOOK_DIR
        self._client = chromadb.Client()
        self._collection = self._client.get_or_create_collection(
            name="runbooks",
            metadata={"hnsw:space": "cosine"},
        )
        self._index_runbooks()

    def _chunk_by_section(self, content: str) -> list[dict]:
        """마크다운을 ## 섹션 기준으로 분할하여 청킹"""
        chunks: list[dict] = []
        current_section = "overview"
        current_lines: list[str] = []
        title = ""

        for line in content.split("\n"):
            if line.startswith("# ") and not title:
                title = line.lstrip("# ").strip()
                current_lines.append(line)
            elif line.startswith("## "):
                if current_lines:
                    chunks.append({
                        "section": current_section,
                        "title": title,
                        "text": "\n".join(current_lines).strip(),
                    })
                current_section = line.lstrip("# ").strip()
                current_lines = [line]
            else:
                current_lines.append(line)

        if current_lines:
            chunks.append({
                "section": current_section,
                "title": title,
                "text": "\n".join(current_lines).strip(),
            })

        return chunks

    def _index_runbooks(self):
        """runbooks/ 디렉토리의 모든 .md 파일을 청킹하여 벡터 DB에 인덱싱"""
        if not self._runbook_dir.exists():
            return

        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict] = []

        for md_file in sorted(self._runbook_dir.glob("*.md")):
            content = md_file.read_text(encoding="utf-8")
            chunks = self._chunk_by_section(content)

            for i, chunk in enumerate(chunks):
                ids.append(f"{md_file.stem}_{i}")
                documents.append(chunk["text"])
                metadatas.append({
                    "source": md_file.name,
                    "title": chunk["title"],
                    "section": chunk["section"],
                })

        if ids:
            self._collection.upsert(ids=ids, documents=documents, metadatas=metadatas)

    def search(self, query: str, n_results: int = 5) -> list[dict]:
        """쿼리와 의미적으로 관련된 런북 조각들을 반환"""
        results = self._collection.query(
            query_texts=[query],
            n_results=min(n_results, self._collection.count()),
        )

        if not results["documents"] or not results["documents"][0]:
            return []

        return [
            {
                "source": meta["source"],
                "title": meta["title"],
                "section": meta["section"],
                "content": doc,
                "relevance_score": round(1 - dist, 4),
            }
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            )
        ]

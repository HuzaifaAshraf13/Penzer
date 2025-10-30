import aiosqlite
from types import SimpleNamespace
from typing import Optional, Any, Dict, List, Tuple
import os
import json
try:
    import numpy as np
    _HAS_NUMPY = True
except Exception:
    np = None
    _HAS_NUMPY = False


class Memory:
    """Memory layer with task queue (SQLite) and optional vector DB (FAISS).

    Summary
    -------
    - Async SQLite-backed task queue for simple task lifecycle storage.
    - Optional FAISS-backed vector index for embeddings and similarity search.
      If FAISS is not available the class falls back to a numpy-based in-memory
      brute-force store which is persisted to disk as `.npy` + metadata JSON.

    Key public async methods
    ------------------------
    - add_task(task_id, command)
    - get_next_task()
    - store_result(task_id, result)
    - add_embedding(emb_id, vector, metadata)
    - search_embeddings(query_vector, top_k)

    Notes
    -----
    - This class tries to be best-effort: missing optional dependencies will
      degrade to a safe fallback rather than raising at import time.
    - Embedding vectors are expected to be float32 lists/arrays. The
      `embedding_dim` parameter enforces dimensionality for both FAISS and
      numpy fallback.

    Example usage (async):
    -----------------------
    async def example():
        mem = Memory(db_path='penzer.db', index_dir='faiss_index', embedding_dim=8)
        await mem.add_task('t1', 'echo hello')
        task = await mem.get_next_task()
        await mem.store_result(task.id, '{"status":"done"}')

        # add/search embeddings
        await mem.add_embedding('doc1', [0.1]*8, metadata={'source': 'test'})
        res = await mem.search_embeddings([0.1]*8, top_k=1)

    """

    def __init__(self, db_path: str = "penzer.db", index_dir: str = "faiss_index", embedding_dim: int = 128):
        self.db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None

        # Vector DB settings
        self.index_dir = index_dir
        self.embedding_dim = embedding_dim
        os.makedirs(self.index_dir, exist_ok=True)

        # Try to use faiss if installed
        self._use_faiss = False
        self._faiss = None
        self._faiss_index = None
        self._intid_to_str: Dict[int, str] = {}
        self._next_int_id = 1

        try:
            import faiss  # type: ignore

            self._faiss = faiss
            # we'll use inner product (dot) for similarity by default
            self._use_faiss = True
        except Exception:
            # faiss not available; fallback to numpy store
            self._use_faiss = False

        # Numpy fallback storage (only if numpy is available)
        self._emb_matrix: Optional[Any] = None
        self._emb_ids: List[str] = []

        # Try loading existing index/metadata
        try:
            self._load_index()
        except Exception:
            # Start fresh if loading fails
            pass

    # --------------------- SQLite task queue ---------------------
    async def _ensure_conn(self):
        if self._conn is None:
            self._conn = await aiosqlite.connect(self.db_path)
            await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                command TEXT,
                status TEXT DEFAULT 'pending',
                result TEXT
            )""")
            await self._conn.commit()

    async def add_task(self, task_id: str, command: str):
        await self._ensure_conn()
        await self._conn.execute(
            "INSERT OR IGNORE INTO tasks (id, command) VALUES (?, ?)",
            (task_id, command)
        )
        await self._conn.commit()

    async def get_next_task(self) -> Optional[Any]:
        await self._ensure_conn()
        cur = await self._conn.execute(
            "SELECT id, command FROM tasks WHERE status='pending' LIMIT 1"
        )
        row = await cur.fetchone()
        if not row:
            return None
        return SimpleNamespace(id=row[0], command=row[1])

    async def store_result(self, task_id: str, result: str):
        await self._ensure_conn()
        await self._conn.execute(
            "UPDATE tasks SET status=?, result=? WHERE id= ?",
            ("done", result, task_id)
        )
        await self._conn.commit()

    async def close(self):
        if self._conn:
            await self._conn.close()
            self._conn = None

    # --------------------- Vector DB API ---------------------
    def _load_index(self):
        """Load persisted index & metadata if present."""
        meta_path = os.path.join(self.index_dir, "meta.json")
        if self._use_faiss and self._faiss is not None:
            index_path = os.path.join(self.index_dir, "index.faiss")
            if os.path.exists(index_path):
                self._faiss_index = self._faiss.read_index(index_path)
            # load mapping
            if os.path.exists(meta_path):
                with open(meta_path, "r", encoding="utf-8") as f:
                    payload = json.load(f)
                self._intid_to_str = {int(k): v for k, v in payload.get("id_map", {}).items()}
                self._next_int_id = payload.get("next_int_id", 1)
        else:
            # numpy fallback
            mat_path = os.path.join(self.index_dir, "embeddings.npy")
            ids_path = os.path.join(self.index_dir, "emb_ids.json")
            if os.path.exists(mat_path) and os.path.exists(ids_path):
                self._emb_matrix = np.load(mat_path)
                with open(ids_path, "r", encoding="utf-8") as f:
                    self._emb_ids = json.load(f)

    def _save_index(self):
        """Persist index & metadata to disk (best-effort)."""
        meta_path = os.path.join(self.index_dir, "meta.json")
        try:
            if self._use_faiss and self._faiss_index is not None:
                index_path = os.path.join(self.index_dir, "index.faiss")
                self._faiss.write_index(self._faiss_index, index_path)
                payload = {"id_map": {str(k): v for k, v in self._intid_to_str.items()}, "next_int_id": self._next_int_id}
                with open(meta_path, "w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2)
            else:
                # numpy fallback persistence
                if self._emb_matrix is not None:
                    mat_path = os.path.join(self.index_dir, "embeddings.npy")
                    np.save(mat_path, self._emb_matrix)
                ids_path = os.path.join(self.index_dir, "emb_ids.json")
                with open(ids_path, "w", encoding="utf-8") as f:
                    json.dump(self._emb_ids, f, indent=2)
        except Exception:
            # best-effort
            pass

    async def add_embedding(self, emb_id: str, vector: List[float], metadata: Optional[Dict[str, Any]] = None) -> None:
        """Add a vector embedding to the vector store.

        emb_id: unique string id for the vector (e.g., doc or task id)
        vector: list/iterable of floats (length must match embedding_dim)
        metadata: optional dict stored in metadata file (not used for search but persisted)
        """
        if not _HAS_NUMPY:
            raise RuntimeError("numpy is required for embeddings. Install numpy or enable FAISS with numpy support.")

        vec = np.asarray(vector, dtype=np.float32)
        if vec.ndim == 1:
            vec = vec.reshape(1, -1)

        if vec.shape[1] != self.embedding_dim:
            raise ValueError(f"Embedding dimension mismatch: expected {self.embedding_dim}, got {vec.shape[1]}")

        if self._use_faiss and self._faiss is not None:
            # prepare index
            if self._faiss_index is None:
                flat = self._faiss.IndexFlatIP(self.embedding_dim)
                # use ID map to preserve string ids via integer mapping
                self._faiss_index = self._faiss.IndexIDMap(flat)

            int_id = self._next_int_id
            self._next_int_id += 1
            self._intid_to_str[int_id] = emb_id

            arr = np.ascontiguousarray(vec)
            self._faiss_index.add_with_ids(arr, np.array([int_id], dtype=np.int64))
            # persist mapping and index
            await self._persist_index_async()
        else:
            # numpy fallback: append to matrix
            if self._emb_matrix is None:
                self._emb_matrix = vec.copy()
            else:
                self._emb_matrix = np.vstack([self._emb_matrix, vec])
            self._emb_ids.append(emb_id)
            await self._persist_index_async()

        # store metadata beside index (append or create metadata file)
        if metadata is not None:
            meta_file = os.path.join(self.index_dir, "metadata.json")
            try:
                existing = {}
                if os.path.exists(meta_file):
                    with open(meta_file, "r", encoding="utf-8") as f:
                        existing = json.load(f)
                existing[emb_id] = metadata
                with open(meta_file, "w", encoding="utf-8") as f:
                    json.dump(existing, f, indent=2)
            except Exception:
                pass

    async def _persist_index_async(self) -> None:
        # run blocking save in a thread to avoid blocking event loop
        await __import__("asyncio").to_thread(self._save_index)

    async def search_embeddings(self, query_vector: List[float], top_k: int = 5) -> List[Tuple[str, float, Dict[str, Any]]]:
        """Search the vector DB and return list of (emb_id, score, metadata).

        Scores are similarity (higher is better) when using inner product.
        """
        if not _HAS_NUMPY:
            raise RuntimeError("numpy is required for searching embeddings")

        q = np.asarray(query_vector, dtype=np.float32)
        if q.ndim == 1:
            q = q.reshape(1, -1)

        if q.shape[1] != self.embedding_dim:
            raise ValueError(f"Query vector dimension mismatch: expected {self.embedding_dim}, got {q.shape[1]}")

            results: List[Tuple[str, float, Dict[str, Any]]] = []

            if self._use_faiss and self._faiss is not None and self._faiss_index is not None:
                D, I = self._faiss_index.search(np.ascontiguousarray(q), top_k)
                # D: distances/similarities, I: int ids
                for score, int_id in zip(D[0].tolist(), I[0].tolist()):
                    if int_id == -1:
                        continue
                    emb_id = self._intid_to_str.get(int(int_id), str(int_id))
                    meta = {}
                    meta_file = os.path.join(self.index_dir, "metadata.json")
                    if os.path.exists(meta_file):
                        try:
                            with open(meta_file, "r", encoding="utf-8") as f:
                                m = json.load(f)
                                meta = m.get(emb_id, {})
                        except Exception:
                            meta = {}
                    results.append((emb_id, float(score), meta))
            else:
                # numpy brute-force similarity (dot product)
                if self._emb_matrix is None or len(self._emb_ids) == 0:
                    return []
                mat = self._emb_matrix  # shape (N, D)
                sims = (mat @ q.T).squeeze(axis=1)
                # get top-k indices
                topk_idx = np.argsort(-sims)[:top_k]
                meta_file = os.path.join(self.index_dir, "metadata.json")
                meta_map = {}
                if os.path.exists(meta_file):
                    try:
                        with open(meta_file, "r", encoding="utf-8") as f:
                            meta_map = json.load(f)
                    except Exception:
                        meta_map = {}
                for idx in topk_idx.tolist():
                    emb_id = self._emb_ids[idx]
                    score = float(sims[idx])
                    meta = meta_map.get(emb_id, {})
                    results.append((emb_id, score, meta))

            return results


    # --------------------- Convenience helpers ---------------------
    def list_embedding_ids(self) -> List[str]:
        """Return a list of embedding ids currently known to the index."""
        if self._use_faiss:
            return list(self._intid_to_str.values())
        return list(self._emb_ids)

    def get_metadata(self, emb_id: str) -> Dict[str, Any]:
        meta_file = os.path.join(self.index_dir, "metadata.json")
        if os.path.exists(meta_file):
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    payload = json.load(f)
                return payload.get(emb_id, {})
            except Exception:
                return {}
        return {}

    async def delete_embedding(self, emb_id: str) -> bool:
        """Delete an embedding by id. Returns True if deleted, False otherwise.

        Note: FAISS deletion is best-effort (IDMap supports removal by id). Numpy
        fallback performs an in-memory filter and rewrites the persisted matrix.
        """
        if self._use_faiss and self._faiss_index is not None:
            # find int id for emb_id
            int_id = None
            for k, v in list(self._intid_to_str.items()):
                if v == emb_id:
                    int_id = k
                    break
            if int_id is None:
                return False
            try:
                # FAISS doesn't provide a standard remove_by_id for IndexIDMap in all builds;
                # attempt to call remove_ids if available.
                self._faiss_index.remove_ids(np.array([int_id], dtype=np.int64))
            except Exception:
                # not supported; mark and continue
                pass
            # remove mapping and persist metadata
            self._intid_to_str.pop(int_id, None)
            await self._persist_index_async()
            return True

        # numpy fallback
        if self._emb_ids and emb_id in self._emb_ids:
            idx = self._emb_ids.index(emb_id)
            if self._emb_matrix is not None:
                self._emb_matrix = np.delete(self._emb_matrix, idx, axis=0)
            self._emb_ids.pop(idx)
            await self._persist_index_async()
            return True
        return False


if __name__ == "__main__":
    # small demo: only runs when the file is executed directly.
    import asyncio

    async def demo():
        print("Memory demo starting")
        mem = Memory(db_path=":memory:", index_dir="faiss_index_demo", embedding_dim=4)
        # add and search embeddings only if numpy is available
        if not _HAS_NUMPY:
            print("numpy not available — skipping embedding demo")
            return

        await mem.add_embedding("doc_demo", [0.1, 0.2, 0.3, 0.4], metadata={"note": "demo"})
        res = await mem.search_embeddings([0.1, 0.2, 0.3, 0.4], top_k=3)
        print("Search results:", res)

    asyncio.run(demo())


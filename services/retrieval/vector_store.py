import os, pickle, numpy as np
from typing import List, Dict
try:
    import faiss
    _HAS_FAISS = True
except Exception:
    _HAS_FAISS = False

from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

MODEL = None

def _load_model():
    global MODEL
    if MODEL is None:
        MODEL = SentenceTransformer('all-MiniLM-L6-v2')
    return MODEL

class SimpleVectorStore:
    def __init__(self, docs: List[str]=None, embeddings=None):
        self.docs = docs or []
        self.embeddings = embeddings if embeddings is not None else (np.zeros((0,384)) if self.docs else np.empty((0,384)))
        self.index = None
        self.dim = 384

    def build_index(self):
        if _HAS_FAISS:
            self.index = faiss.IndexFlatIP(self.dim)
            # normalize for cosine via inner product
            faiss.normalize_L2(self.embeddings)
            self.index.add(self.embeddings)
        else:
            self.index = None

    def add(self, docs: List[str]):
        model = _load_model()
        embs = model.encode(docs, show_progress_bar=False)
        if self.embeddings.shape[0]==0:
            self.embeddings = np.asarray(embs)
        else:
            self.embeddings = np.vstack([self.embeddings, np.asarray(embs)])
        self.docs.extend(docs)
        self.build_index()

    def save(self, path):
        with open(path, 'wb') as f:
            pickle.dump({'docs': self.docs, 'embeddings': self.embeddings}, f)

    @classmethod
    def load(cls, path):
        if not os.path.exists(path):
            return SimpleVectorStore()
        with open(path, 'rb') as f:
            data = pickle.load(f)
        obj = SimpleVectorStore(data.get('docs', []), data.get('embeddings', None))
        obj.build_index()
        return obj

    def top_k(self, query, top_k=3):
        model = _load_model()
        q_emb = model.encode([query])
        if _HAS_FAISS and self.index is not None:
            import numpy as _np
            qn = _np.array(q_emb).astype('float32')
            faiss.normalize_L2(qn)
            D, I = self.index.search(qn, top_k)
            res = []
            for idx, dist in zip(I[0], D[0]):
                if idx < len(self.docs):
                    res.append({'id': str(idx), 'text': self.docs[idx], 'score': float(dist)})
            return res
        else:
            sims = cosine_similarity(q_emb, self.embeddings)[0]
            idxs = sims.argsort()[::-1][:top_k]
            return [{'id': str(int(i)), 'text': self.docs[int(i)], 'score': float(sims[int(i)])} for i in idxs]

# Global store instance
STORE = None
STORE_PATH = os.getenv('RAG_VECTOR_DB_PATH','/mnt/data/rag_vectors.pkl')

def init_store(path=None):
    global STORE, STORE_PATH
    if path:
        STORE_PATH = path
    STORE = SimpleVectorStore.load(STORE_PATH)

def persist_store():
    global STORE, STORE_PATH
    if STORE is not None:
        STORE.save(STORE_PATH)

def add_documents(docs: List[str]):
    global STORE
    if STORE is None:
        init_store()
    STORE.add(docs)
    persist_store()

def top_k(query, top_k=3):
    global STORE
    if STORE is None:
        init_store()
    return STORE.top_k(query, top_k=top_k)

def multi_hop(query, top_k=3, hops=2, expansion_k=2):
    # Simple multi-hop: retrieve passages, create expanded query by concatenating top sentences from results, then retrieve again
    global STORE
    if STORE is None:
        init_store()
    results = STORE.top_k(query, top_k=top_k)
    expanded = query
    for r in results[:expansion_k]:
        # take first 20 words of passage as expansion
        expanded += ' ' + ' '.join(r['text'].split()[:20])
    # second pass
    more = STORE.top_k(expanded, top_k=top_k)
    # merge unique ids preserving order
    seen = set()
    merged = []
    for r in results + more:
        if r['id'] not in seen:
            merged.append(r); seen.add(r['id'])
    return merged

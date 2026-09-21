from functools import lru_cache
import os

import numpy as np

from app.config import get_settings


class LocalEmbedder:
    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        os.environ.setdefault("HF_HOME", str(self.settings.model_cache))
        os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
        os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
        from sentence_transformers import SentenceTransformer
        import torch
        torch.set_num_threads(self.settings.embedding_threads)
        self.model = SentenceTransformer(
            self.settings.embedding_model, revision=self.settings.embedding_revision,
            cache_folder=str(self.settings.model_cache), device=self.settings.embedding_device,
            trust_remote_code=False,
        )
        self.dimensions = self.model.get_sentence_embedding_dimension()
        if not self.dimensions:
            raise ValueError("Embedding model did not report its dimensions")
        self.max_tokens = self.model.max_seq_length
        self.tokenizer = self.model.tokenizer

    def token_count(self, text):
        return len(self.tokenizer.encode(text, add_special_tokens=True, truncation=False, verbose=False))

    def encode(self, texts, *, query=False):
        if not texts:
            return []
        if any(self.token_count(text) > self.max_tokens for text in texts):
            raise ValueError("Embedding input exceeds model context; silent truncation refused")
        # Explicitly support asymmetric retrieval models, as well as MiniLM.
        method = "encode_query" if query else "encode_document"
        encoder = getattr(self.model, method, self.model.encode)
        vectors = encoder(texts, batch_size=self.settings.embedding_batch_size,
                          normalize_embeddings=True, show_progress_bar=False,
                          convert_to_numpy=True)
        if vectors.shape != (len(texts), self.dimensions) or not np.isfinite(vectors).all():
            raise ValueError("Invalid embedding shape or non-finite vectors")
        if np.any(np.linalg.norm(vectors, axis=1) == 0):
            raise ValueError("Zero embeddings cannot support cosine retrieval")
        return vectors.tolist()


@lru_cache
def get_embedder():
    return LocalEmbedder()

from sentence_transformers import SentenceTransformer
from core.qdrant_client_init import qdrant_client
import os
class Embedding:
    def __init__(self):
        self.client = qdrant_client.client
        self.model = SentenceTransformer(os.getenv("MODEL_NAME"))
        
embedding = Embedding()
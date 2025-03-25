from sentence_transformers import SentenceTransformer
from common.core.qdrant_client_init import qdrant_client

class Embedding:
    def __init__(self):
        self.client = qdrant_client.client
        self.model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        
embedding = Embedding()
from qdrant_client import QdrantClient
from qdrant_client.http import models
import os

class qdrant_client:
    def __init__(self):
        self.client = QdrantClient(
            url=os.getenv("QDRANT_CLOUD_URL"),
            api_key=os.getenv("QDRANT_API_KEY")
        )
        
qdrant_client = qdrant_client()

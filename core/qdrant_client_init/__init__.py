from qdrant_client import AsyncQdrantClient
import os
import httpx

class QdrantClient:
    def __init__(self):
        self.client = AsyncQdrantClient(
            url=os.getenv("QDRANT_CLOUD_URL"),
            api_key=os.getenv("QDRANT_API_KEY"),
            timeout=60.0,
            limits=httpx.Limits(
                max_connections=100,
                max_keepalive_connections=20,
                keepalive_expiry=60
            ),
            prefer_grpc=True,
            grpc_options={
                "grpc.max_send_message_length": 50 * 1024 * 1024, 
                "grpc.max_receive_message_length": 50 * 1024 * 1024
            }
        )

qdrant_client = QdrantClient()

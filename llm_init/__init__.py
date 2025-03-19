import os
from openai import OpenAI
from fastapi import HTTPException

class DeepseekClient:
    def __init__(self):
        self.client = None
        
    def initialize(self):
        """ Deepseek init """
        api_key = os.getenv("DEEPSEEK_API_KEY")
        base_url = os.getenv("DEEPSEEK_BASE_URL")
        
        if not api_key or not base_url:
            raise HTTPException(
                status_code=500,
                detail=" Deepseek API init fail"
            )
            
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        return self.client

deepseek = DeepseekClient()  
import asyncio, re

from typing import Optional
from core.llm_init.prompt import PromptTemplates
from models.dto.resultdto import ResultDTO
from models.request.articleRequest import ArticleGenerationRequest
from helper.llmStreamHelper import LLMStreamHelper

class ArticleService:
    def __init__(self):
        self.max_tokens: Optional[int] = 1024 
        self.temperature: Optional[float] = 0.7
        self.default_model = "deepseek-chat"
        self.prompt_templates = PromptTemplates()
        
        self.api_retry_attempts = 3
        self.api_timeout = 10 
        
        self.llm_stream_helper = LLMStreamHelper(
            prompt_templates=self.prompt_templates,
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )

    def split_article(self, content: str):
        sections = re.split(r'\\n', content)
        
        cleaned_sections = [
            section.strip() 
            for section in sections 
            if section.strip()
        ]
        
        return ResultDTO.ok(data=cleaned_sections)
        
    async def stream_generate_article(self, request: ArticleGenerationRequest):
        async def event_stream():
            client_disconnected = [False]

            try:
                messages = [
                    {"role": "system", "content": self.prompt_templates.article_writer},
                    {"role": "user", "content": request.prompt}
                ]

                async for data_chunk, content in self.llm_stream_helper.handle_stream_response(
                    enhanced_messages=messages,
                    task=asyncio.current_task(),
                    client_disconnected=client_disconnected
                ):
                    yield data_chunk
                
                yield "event: end\ndata: {}\n\n"

            except Exception as e:
                error_msg = str(e)
                yield self.llm_stream_helper.generate_error_event(error_msg)

        return self.llm_stream_helper.create_streaming_response(event_stream())
        
    
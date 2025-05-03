import json
import asyncio
from functools import partial
from fastapi.responses import StreamingResponse
from common.core.llm_init import deepseek

class LLMStreamHelper:
    def __init__(self, prompt_templates, temperature=0.7, max_tokens=3000):
        self.prompt_templates = prompt_templates
        self.temperature = temperature
        self.max_tokens = max_tokens

    def generate_enhanced_messages(self, search_result, chat_history: dict):
        context_str = "\n".join([item.text for item in search_result.data])
        system_prompt = self.prompt_templates.rag_analyst(context_str)
        filtered_messages = [msg for msg in chat_history["messages"] if msg["role"] != "system"]
        return [self.create_base_message("system", system_prompt), *filtered_messages]

    @staticmethod
    def create_base_message(role: str, content: str) -> dict:
        return {"role": role, "content": content.strip()}

    async def deepseek_stream(self, messages: list, stream: bool = True, timeout: int = 30):
        try:
            return await asyncio.wait_for(
                deepseek.client.chat.completions.create(
                    model="deepseek-chat",
                    messages=messages,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    stream=stream
                ),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            print("LLM request timeout")
            raise
        except Exception as e:
            print(f"LLM API error: {str(e)}")
            raise

    async def handle_stream_response(self, enhanced_messages: list, task, client_disconnected: list):
        buffer = ""
        llm_task = None
        
        try:
            llm_task = asyncio.create_task(
                self.deepseek_stream(enhanced_messages, stream=True)
            )
            stream = await llm_task
            
            async for chunk in stream:
                if task.done() or client_disconnected[0]:
                    break
                    
                if content := getattr(chunk.choices[0].delta, 'content', None):
                    buffer += content
                    try:
                        yield await self.generate_event_data(buffer), buffer
                        buffer = ""
                    except Exception as e:
                        client_disconnected[0] = True
                        raise e

            if buffer:
                yield await self.generate_event_data(buffer), buffer

        finally:
            if llm_task and not llm_task.done():
                llm_task.cancel()
                try:
                    await llm_task
                except asyncio.CancelledError:
                    pass

    @staticmethod
    async def generate_event_data(content: str) -> str:
        data = await asyncio.to_thread(json.dumps, {"content": content})
        return f"data: {data}\n\n"

    @staticmethod
    def generate_error_event(error_msg: str) -> str:
        return f"event: error\ndata: {json.dumps({'message': error_msg})}\n\n"

    @staticmethod
    def create_streaming_response(event_stream):
        return StreamingResponse(
            event_stream,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )

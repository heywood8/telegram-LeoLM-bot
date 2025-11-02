"""Ollama LLM Provider"""

from typing import List, Dict, Optional, Union, AsyncGenerator
import structlog
import json
import aiohttp
import shutil

from bot.llm.base import BaseLLMProvider, LLMError
from bot.config import config

logger = structlog.get_logger()


class OllamaProvider(BaseLLMProvider):
    """Provider that runs models via Ollama (local CLI or cloud HTTP API).

    Behavior:
    - If the `ollama` CLI is available in PATH, the provider will use it to run
      local models: `ollama run <model> <prompt>`.
    - Otherwise, if `llm_config.base_url` is set (and optionally `api_key`),
      the provider will POST JSON to that URL. The request body is:
        {"model": model_name, "prompt": prompt, "max_tokens": max_tokens, "temperature": temperature}

    Note: The exact HTTP contract is left intentionally generic; set `base_url`
    to the proper Ollama Cloud endpoint (for example `https://api.ollama.ai/generate`).
    """

    def __init__(self, llm_config = config.llm):
        self.model_name = llm_config.model_name
        self.base_url = llm_config.base_url
        self.api_key = llm_config.api_key
        self.timeout = llm_config.timeout

        # prefer local CLI if available
        self._cli_available = shutil.which("ollama") is not None

    def _build_prompt(self, messages: List[Dict[str, str]]) -> str:
        parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            parts.append(f"[{role}] {content}")
        return "\n\n".join(parts)

    async def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        tools: Optional[List[Dict]] = None,
        stream: bool = False
    ) -> Union[str, AsyncGenerator[str, None]]:
        if self._cli_available:
            # Use local ollama CLI (tools not supported in CLI mode, convert to prompt)
            prompt = self._build_prompt(messages)
            return await self._generate_with_cli(prompt, max_tokens, temperature, stream)
        else:
            # Use HTTP API with proper message structure for tool calling
            if not self.base_url:
                raise LLMError("No ollama CLI and no base_url configured for Ollama HTTP API")
            return await self._generate_with_http_messages(messages, max_tokens, temperature, stream, tools)

    async def _generate_with_cli(self, prompt: str, max_tokens: int, temperature: float, stream: bool):
        cmd = ["ollama", "run", self.model_name]

        # For large prompts it's safer to pass via stdin
        proc = await asyncio.create_subprocess_exec(*cmd, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)

        try:
            stdout, stderr = await proc.communicate(input=prompt.encode("utf-8"))
        except Exception as e:
            proc.kill()
            raise LLMError(f"ollama CLI error: {e}")

        if proc.returncode != 0:
            raise LLMError(f"ollama CLI failed: {stderr.decode('utf-8', errors='ignore')}")

        text = stdout.decode("utf-8", errors="ignore")
        return text.strip()

    async def _generate_with_http_messages(self, messages: List[Dict[str, str]], max_tokens: int, temperature: float, stream: bool, tools: Optional[List[Dict]] = None):
        # Ollama exposes two main HTTP endpoints:
        # - POST /api/generate for single-turn generation (prompt string)
        # - POST /api/chat for chat-style messages (list of message objects)
        # Use the chat endpoint with proper message structure for tool calling support

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        url = self.base_url.rstrip("/") + "/api/chat"

        payload = {
            "model": self.model_name,
            "messages": messages,  # Pass messages directly, don't convert to prompt
            "stream": bool(stream),
            # Ollama supports an `options` field for model params; map temperature into it
            "options": {"temperature": temperature} if temperature is not None else {},
        }
        
        # Add tools if provided (for models that support function calling)
        if tools:
            payload["tools"] = tools
            logger.info(f"Sending {len(tools)} tools to Ollama API", tool_names=[t.get('function', {}).get('name') for t in tools])

        session_timeout = aiohttp.ClientTimeout(total=self.timeout)
        sess = aiohttp.ClientSession(timeout=session_timeout)

        if stream:
            # Return an async generator that yields incremental text as JSON objects arrive
            async def stream_gen():
                async with sess as s:
                    async with s.post(url, json=payload, headers=headers) as resp:
                        if resp.status >= 400:
                            text = await resp.text()
                            raise LLMError(f"Ollama HTTP API error: {resp.status} {text}")

                        # The API streams newline-delimited JSON objects. Read line by line.
                        async for raw_line in resp.content:
                            try:
                                line = raw_line.decode("utf-8").strip()
                            except Exception:
                                continue
                            if not line:
                                continue
                            # Some servers stream concatenated JSON objects; try to split by newline
                            for part in line.splitlines():
                                part = part.strip()
                                if not part:
                                    continue
                                try:
                                    obj = json.loads(part)
                                except Exception:
                                    # If not valid JSON, skip
                                    continue

                                # Handle chat stream object shapes
                                # Examples: {"message": {"role":"assistant","content":"The"}, "done": false}
                                if isinstance(obj, dict):
                                    if "message" in obj and isinstance(obj["message"], dict):
                                        content = obj["message"].get("content")
                                        if content:
                                            yield content
                                    elif "response" in obj:
                                        # generate endpoint uses `response` key
                                        if obj.get("response"):
                                            yield obj.get("response")

                        # stream finished
            return stream_gen()

        # non-streaming: single JSON response
        async with sess as s:
            async with s.post(url, json=payload, headers=headers) as resp:
                if resp.status >= 400:
                    text = await resp.text()
                    
                    # If tools were sent and we got an error, retry without tools (model may not support them)
                    if tools and resp.status >= 500:
                        logger.warning(f"Ollama API error with tools (status {resp.status}), retrying without tools")
                        payload_without_tools = {k: v for k, v in payload.items() if k != "tools"}
                        
                        async with s.post(url, json=payload_without_tools, headers=headers) as retry_resp:
                            if retry_resp.status >= 400:
                                retry_text = await retry_resp.text()
                                raise LLMError(f"Ollama HTTP API error (retry without tools): {retry_resp.status} {retry_text}")
                            data = await retry_resp.json()
                    else:
                        raise LLMError(f"Ollama HTTP API error: {resp.status} {text}")
                else:
                    data = await resp.json()

        # Typical successful shapes: {"message": {"content": "...", "tool_calls": [...]}} or {"response": "..."}
        if isinstance(data, dict):
            if "message" in data and isinstance(data["message"], dict):
                message_data = data["message"]
                
                # Check if there are tool_calls in the response
                if "tool_calls" in message_data and message_data["tool_calls"]:
                    # Return a mock OpenAI-like message object with tool_calls
                    logger.info(f"Ollama returned {len(message_data['tool_calls'])} tool calls")
                    
                    class OllamaMessage:
                        def __init__(self, content, tool_calls):
                            self.content = content
                            self.tool_calls = []
                            
                            # Convert Ollama tool_calls to OpenAI format
                            # Ollama format: [{"function": {"name": "...", "arguments": {...}}}]
                            # OpenAI format: [{"id": "...", "type": "function", "function": {"name": "...", "arguments": "{...}"}}]
                            for idx, tc in enumerate(tool_calls):
                                class ToolCall:
                                    def __init__(self, call_id, function_name, arguments):
                                        self.id = call_id
                                        self.type = "function"
                                        
                                        class Function:
                                            def __init__(self, name, args):
                                                self.name = name
                                                # arguments should be a JSON string
                                                self.arguments = json.dumps(args) if isinstance(args, dict) else args
                                        
                                        self.function = Function(function_name, arguments)
                                
                                # Ollama format doesn't have 'id' or 'type' fields at the top level
                                # Only {"function": {"name": "...", "arguments": {...}}}
                                if "function" in tc:
                                    func_data = tc["function"]
                                    function_name = func_data.get("name")
                                    arguments = func_data.get("arguments", {})
                                    # Generate a unique ID for this tool call
                                    call_id = f"call_{function_name}_{idx}"
                                    
                                    self.tool_calls.append(ToolCall(
                                        call_id,
                                        function_name,
                                        arguments
                                    ))
                    
                    return OllamaMessage(
                        message_data.get("content", ""),
                        message_data["tool_calls"]
                    )
                
                # No tool calls, just return content
                return message_data.get("content", "")
            
            if "response" in data:
                return data.get("response", "")

        return json.dumps(data)

    async def _stream_generate(self, *args, **kwargs) -> AsyncGenerator[str, None]:
        # Streaming from Ollama CLI could be implemented by reading stdout incrementally.
        # For simplicity, we reuse the non-streaming path.
        result = await self.generate(*args, **kwargs)
        async def gen():
            yield result
        return gen()

    async def get_embeddings(self, text: str) -> List[float]:
        # Ollama CLI doesn't currently expose embeddings via CLI in a standard way.
        # If using an HTTP API that supports embeddings, the base_url should point to it.
        if self._cli_available:
            raise LLMError("Embeddings unavailable via local ollama CLI")

        # Try HTTP embeddings endpoint convention: base_url + '/embed' or '/embeddings'
        for suffix in ["/embed", "/embeddings", "/v1/embeddings"]:
            url = self.base_url.rstrip("/") + suffix
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as sess:
                async with sess.post(url, json={"model": self.model_name, "input": text}, headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else None) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        # Common shape: {'data':[{'embedding':[...]}]}
                        if isinstance(data, dict) and "data" in data and isinstance(data["data"], list) and data["data"]:
                            return data["data"][0].get("embedding", [])

        raise LLMError("Embeddings not supported for this Ollama configuration")

    def get_token_count(self, text: str) -> int:
        # Ollama doesn't expose tokenizer; provide a rough estimate
        return max(1, len(text) // 4)

    async def health_check(self) -> bool:
        if self._cli_available:
            try:
                proc = await asyncio.create_subprocess_exec("ollama", "list", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                stdout, stderr = await proc.communicate()
                if proc.returncode != 0:
                    return False
                return self.model_name in stdout.decode("utf-8", errors="ignore")
            except Exception:
                return False

        # HTTP mode: try a lightweight request
        if not self.base_url:
            return False
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as sess:
                headers = {}
                if self.api_key:
                    headers["Authorization"] = f"Bearer {self.api_key}"
                async with sess.get(self.base_url, headers=headers) as resp:
                    return resp.status == 200
        except Exception:
            return False

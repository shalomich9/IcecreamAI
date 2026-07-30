import asyncio
import json
import httpx
from openai import AsyncOpenAI
from config import config

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"

# We initialize clients for each agent using their specific keys
clients = {
    "DeepSeek": AsyncOpenAI(api_key=config.DEEPSEEK_API_KEY, base_url=NVIDIA_BASE_URL),
    "GLM": AsyncOpenAI(api_key=config.GLM_API_KEY, base_url=NVIDIA_BASE_URL),
    "Qwen": AsyncOpenAI(api_key=config.QWEN_API_KEY, base_url=NVIDIA_BASE_URL),
    # Using DeepSeek's key or GLM's key for Evaluator if we don't have a specific one. Let's use DeepSeek's key as fallback
    "Evaluator": AsyncOpenAI(api_key=config.DEEPSEEK_API_KEY, base_url=NVIDIA_BASE_URL),
}

# The specific models to use in NIM
MODELS = {
    # DeepSeek v4 Pro/R1 equivalent or fallback (NVIDIA NIM supports deepseek-coder-6.7b-instruct etc. 
    # we'll use a placeholder or general model if exact isn't available, but user said DeepSeek v4 Pro / R1.
    # Llama 3.1 70B is a good proxy if DeepSeek string fails, but we'll try to use the ones provided)
    # Using specific model names for NVIDIA NIM:
    "DeepSeek": "deepseek-ai/deepseek-r1", # Might need adjustment depending on NVIDIA NIM actual deployment names
    "GLM": "zhipuai/glm-4-9b-chat", # GLM 5.2 might be coming, let's use a generic GLM placeholder
    "Qwen": "qwen/qwen2.5-72b-instruct",
    "Evaluator": "meta/llama-3.1-405b-instruct",
}

async def search_tavily(query: str) -> str:
    """Perform a web search using Tavily API."""
    if not config.TAVILY_API_KEY:
        return "Web search is currently disabled (no API key)."
    
    url = "https://api.tavily.com/search"
    headers = {"Content-Type": "application/json"}
    data = {
        "api_key": config.TAVILY_API_KEY,
        "query": query,
        "search_depth": "basic",
        "include_answer": True,
        "max_results": 3
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, headers=headers, json=data)
            response.raise_for_status()
            result = response.json()
            
            # Combine the results into a readable context
            context = f"Tavily Answer: {result.get('answer', '')}\n\nSources:\n"
            for res in result.get('results', []):
                context += f"- {res['title']}: {res['content']}\n"
            return context
        except Exception as e:
            return f"Error during web search: {e}"

# Tool schema for OpenAI compatible endpoints
tavily_tool = {
    "type": "function",
    "function": {
        "name": "search_internet",
        "description": "Поиск актуальной информации в интернете.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Поисковый запрос.",
                }
            },
            "required": ["query"],
        },
    }
}

async def generate_response(agent_name: str, messages: list, use_tools: bool = True, stream: bool = True):
    """Generate a response using the appropriate agent and its specific API key."""
    client = clients.get(agent_name)
    model = MODELS.get(agent_name)
    
    if not client:
        yield "Error: Client not found for agent."
        return

    kwargs = {
        "model": model,
        "messages": messages,
        "temperature": 0.7,
        "stream": stream,
    }
    
    if use_tools:
        kwargs["tools"] = [tavily_tool]
        kwargs["tool_choice"] = "auto"
    
    try:
        if stream:
            stream_response = await client.chat.completions.create(**kwargs)
            
            # Handle tool calls in stream (simplified for now, full tool calling in streams can be complex)
            # To keep it robust, we'll collect the whole response if tools are called, or stream if not.
            # Wait, tool calls in stream require buffering. Let's do non-streaming for tool calls first, 
            # and then stream the final answer. 
            
            # Actually, standard streaming approach:
            tool_calls = []
            full_content = ""
            
            async for chunk in stream_response:
                delta = chunk.choices[0].delta
                
                # Check for tool calls
                if delta.tool_calls:
                    for tc_chunk in delta.tool_calls:
                        if len(tool_calls) <= tc_chunk.index:
                            tool_calls.append({"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
                        tc = tool_calls[tc_chunk.index]
                        
                        if tc_chunk.id: tc["id"] += tc_chunk.id
                        if tc_chunk.function.name: tc["function"]["name"] += tc_chunk.function.name
                        if tc_chunk.function.arguments: tc["function"]["arguments"] += tc_chunk.function.arguments
                
                elif delta.content:
                    full_content += delta.content
                    yield {"type": "content", "data": delta.content}
            
            if tool_calls:
                yield {"type": "status", "data": "Ищу информацию в интернете..."}
                messages.append({"role": "assistant", "content": None, "tool_calls": tool_calls})
                
                for tool_call in tool_calls:
                    if tool_call["function"]["name"] == "search_internet":
                        try:
                            args = json.loads(tool_call["function"]["arguments"])
                            query = args.get("query")
                            search_result = await search_tavily(query)
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call["id"],
                                "name": tool_call["function"]["name"],
                                "content": search_result
                            })
                        except Exception as e:
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call["id"],
                                "name": tool_call["function"]["name"],
                                "content": f"Error parsing tool args: {e}"
                            })
                
                # Yield the status that we are analyzing the search results
                yield {"type": "status", "data": "Анализирую результаты поиска..."}
                
                # Recursively call without tools to get the final answer based on search
                async for item in generate_response(agent_name, messages, use_tools=False, stream=True):
                    yield item

        else:
            # Non-streaming
            response = await client.chat.completions.create(**kwargs)
            message = response.choices[0].message
            if message.tool_calls:
                messages.append(message)
                for tool_call in message.tool_calls:
                    if tool_call.function.name == "search_internet":
                        args = json.loads(tool_call.function.arguments)
                        search_result = await search_tavily(args.get("query"))
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": tool_call.function.name,
                            "content": search_result
                        })
                # Re-call without tools
                async for item in generate_response(agent_name, messages, use_tools=False, stream=False):
                    yield item
            else:
                yield message.content
    except Exception as e:
        yield {"type": "error", "data": f"API Error: {e}"}

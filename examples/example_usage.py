"""
Примеры использования CoreML RAG MCP Prompt Service
"""
import asyncio
import httpx


async def example_query():
    """Пример обработки запроса"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/query",
            json={
                "query": "Какие права у меня при расторжении договора аренды?",
                "llm_provider": "openai",
                "model": "gpt-3.5-turbo",
                "use_rag": True,
                "use_law": True
            }
        )
        result = response.json()
        print("Ответ:", result["answer"])
        print("Источники:", result["sources"])


async def example_stream_query():
    """Пример потоковой обработки запроса"""
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            "http://localhost:8000/query/stream",
            json={
                "query": "Что такое трудовой договор?",
                "llm_provider": "openai"
            }
        ) as response:
            async for chunk in response.aiter_text():
                print(chunk, end="", flush=True)


async def example_add_document():
    """Пример добавления документа"""
    async with httpx.AsyncClient() as client:
        with open("path/to/document.pdf", "rb") as f:
            files = {"file": ("document.pdf", f, "application/pdf")}
            response = await client.post(
                "http://localhost:8000/rag/add-document",
                files=files
            )
            print(response.json())


async def example_search_rag():
    """Пример поиска в RAG"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "http://localhost:8000/rag/search",
            params={"query": "договор аренды", "top_k": 5}
        )
        result = response.json()
        print("Результаты поиска:", result["results"])


async def example_search_cases():
    """Пример поиска судебных дел"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/mcp/law/search-cases",
            params={
                "query": "расторжение договора",
                "instance": "3",
                "limit": 10
            }
        )
        result = response.json()
        print("Найденные дела:", result["results"])


if __name__ == "__main__":
    # Раскомментируйте нужный пример
    # asyncio.run(example_query())
    # asyncio.run(example_stream_query())
    # asyncio.run(example_add_document())
    # asyncio.run(example_search_rag())
    # asyncio.run(example_search_cases())
    pass


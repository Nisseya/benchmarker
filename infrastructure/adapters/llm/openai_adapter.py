import httpx
from domain.ports.llm import LLMProviderPort

class OpenAIAdapter(LLMProviderPort):
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.url = "https://api.openai.com/v1/chat/completions"

    async def generate_code(self, prompt: str, model_name: str, context_schema: dict) -> str:
        """
        Envoie la question et le schéma au LLM pour obtenir du code pur.
        """
        system_prompt = (
            "You are a world-class data scientist. Output ONLY raw code. "
            "No markdown blocks, no explanations. "
            f"Context schema: {context_schema}"
        )
        
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Task: {prompt}"}
            ],
            "temperature": 0
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(self.url, json=payload, headers=headers, timeout=30.0)
            result = response.json()
            # Nettoyage du code (au cas où le LLM met des backticks)
            code = result['choices'][0]['message']['content']
            return code.replace("```python", "").replace("```sql", "").replace("```", "").strip()
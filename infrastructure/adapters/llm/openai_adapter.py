import httpx
from typing import Any

from domain.ports.llm import LLMProviderPort


class OpenAIAdapter(LLMProviderPort):
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.url = "https://api.openai.com/v1/chat/completions"

    async def generate_code(self, prompt: str, model_name: str, context_schema: dict) -> str:
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
                {"role": "user", "content": f"Task: {prompt}"},
            ],
            "temperature": 0,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(self.url, json=payload, headers=headers, timeout=30.0)
            response.raise_for_status()
            result = response.json()

        code = result["choices"][0]["message"]["content"]
        return code.replace("```python", "").replace("```sql", "").replace("```", "").strip()

    async def judge_answer(
        self,
        question: str,
        code: str,
        output: Any,
        model_name: str,
    ) -> float:
        """
        Note la pertinence (0.0 à 1.0) via un LLM.
        """
        system_prompt = (
            "You are a strict evaluator. "
            "Return ONLY a number between 0.0 and 1.0. "
            "No text, no JSON, no explanation."
        )

        user_prompt = (
            f"Question:\n{question}\n\n"
            f"Generated code:\n{code}\n\n"
            f"Program output:\n{output}\n\n"
            "Score (0.0 to 1.0):"
        )

        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(self.url, json=payload, headers=headers, timeout=30.0)
            response.raise_for_status()
            result = response.json()

        raw = result["choices"][0]["message"]["content"].strip()

        try:
            score = float(raw)
        except ValueError:
            score = 0.0

        if score < 0.0:
            return 0.0
        if score > 1.0:
            return 1.0
        return score

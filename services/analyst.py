"""
AI Analyst Service - Model agnostic.
Works with: OpenAI GPT, Anthropic Claude, MiniMax, DeepSeek, Ollama.
"""

from __future__ import annotations
import os
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal, Optional
from pathlib import Path
from loguru import logger

Provider = Literal["openai", "anthropic", "minimax", "deepseek", "ollama", "mock"]

@dataclass
class ModelConfig:
    provider: Provider = "openai"
    model: str = "gpt-4"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    max_tokens: int = 4096
    temperature: float = 0.7

@dataclass
class AnalysisResult:
    summary: str
    trades_analyzed: int
    win_rate: float
    profit_factor: float
    issues_found: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    pattern_analysis: str = ""
    risk_assessment: str = ""
    improvement_plan: str = ""
    raw_response: Optional[str] = None

class LLMProvider(ABC):
    @abstractmethod
    def complete(self, prompt: str, system: str = "") -> str:
        pass

class OpenAIProvider(LLMProvider):
    def __init__(self, config: ModelConfig):
        self.config = config
        self.api_key = config.api_key or os.getenv("OPENAI_API_KEY", "")
        self.base_url = config.base_url or "https://api.openai.com/v1"

    def complete(self, prompt: str, system: str = "") -> str:
        try:
            import openai
            client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            response = client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature
            )
            return response.choices[0].message.content
        except ImportError:
            return self._mock()
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise

    def _mock(self) -> str:
        return "Configure OPENAI_API_KEY for real responses."

class AnthropicProvider(LLMProvider):
    def __init__(self, config: ModelConfig):
        self.config = config
        self.api_key = config.api_key or os.getenv("ANTHROPIC_API_KEY", "")

    def complete(self, prompt: str, system: str = "") -> str:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=self.api_key)
            response = client.messages.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except ImportError:
            return self._mock()
        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            raise

    def _mock(self) -> str:
        return "Configure ANTHROPIC_API_KEY for real responses."

class MiniMaxProvider(LLMProvider):
    def __init__(self, config: ModelConfig):
        self.config = config
        self.api_key = config.api_key or os.getenv("MINIMAX_API_KEY", "")
        self.base_url = config.base_url or "https://api.minimax.chat/v1"

    def complete(self, prompt: str, system: str = "") -> str:
        try:
            import openai
            client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            response = client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"MiniMax API error: {e}")
            return f"MiniMax error: {e}"

    def _mock(self) -> str:
        return "Configure MINIMAX_API_KEY for real responses."

class DeepSeekProvider(LLMProvider):
    def __init__(self, config: ModelConfig):
        self.config = config
        self.api_key = config.api_key or os.getenv("DEEPSEEK_API_KEY", "")
        self.base_url = config.base_url or "https://api.deepseek.com/v1"

    def complete(self, prompt: str, system: str = "") -> str:
        try:
            import openai
            client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            response = client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"DeepSeek API error: {e}")
            return f"DeepSeek error: {e}"

    def _mock(self) -> str:
        return "Configure DEEPSEEK_API_KEY for real responses."

class OllamaProvider(LLMProvider):
    def __init__(self, config: ModelConfig):
        self.config = config
        self.base_url = config.base_url or "http://localhost:11434/v1"
        self.api_key = "ollama"

    def complete(self, prompt: str, system: str = "") -> str:
        try:
            import openai
            client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            response = client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Ollama error: {e}")
            return f"Ollama error: {e}"

    def _mock(self) -> str:
        return "Start Ollama server for local models."

class MockProvider(LLMProvider):
    def __init__(self, config: ModelConfig):
        self.config = config

    def complete(self, prompt: str, system: str = "") -> str:
        return f"[MOCK] Analyzed with {self.config.provider}/{self.config.model}. Prompt: {len(prompt)} chars. Set API key for real analysis."

def create_provider(config: ModelConfig) -> LLMProvider:
    providers = {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "minimax": MiniMaxProvider,
        "deepseek": DeepSeekProvider,
        "ollama": OllamaProvider,
        "mock": MockProvider
    }
    provider_class = providers.get(config.provider, OpenAIProvider)
    return provider_class(config)
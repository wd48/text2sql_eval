from langchain_ollama import ChatOllama
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

""" OllamaLLMManager 클래스는 LangChain을 활용하여 Ollama LLM과의 상호작용을 간소화하는 공통 관리 클래스입니다.
- 모델 초기화, 프롬프트 템플릿 관리, 출력 파싱을 통합하여 LLM 호출을 단일 메서드로 간편하게 수행할 수 있도록 설계되었습니다.
- 다양한 프롬프트 템플릿을 지원하여 유연한 LLM 활용이 가능하며, 단발성 호출을 위한 유틸리티 메서드도 포함되어 있습니다.
"""
class OllamaLLMManager:
    """LangChain을 활용한 Ollama LLM 공통 관리 클래스"""

    def __init__(self, model_name: str = "llama3", temperature: float = 0.0):
        # SQL 생성과 같은 결정론적(Deterministic) 작업이므로 temperature를 0에 가깝게 설정
        self.llm = ChatOllama(model=model_name, temperature=temperature)
        self.output_parser = StrOutputParser()

    def get_chain(self, prompt_template_str: str):
        """
        프롬프트 템플릿 문자열을 받아 LangChain (Prompt | LLM | Parser) 파이프라인을 반환합니다.
        """
        prompt = PromptTemplate.from_template(prompt_template_str)
        chain = prompt | self.llm | self.output_parser
        return chain

    def invoke(self, prompt_template_str: str, **kwargs) -> str:
        """
        단발성으로 LLM을 호출할 때 사용하는 유틸리티 메서드
        """
        chain = self.get_chain(prompt_template_str)
        return chain.invoke(kwargs).strip()
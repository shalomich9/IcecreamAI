import streamlit as st

def get_secret(key: str, default: str = "") -> str:
    """Safely fetch secrets in Streamlit context or fallback to default."""
    try:
        return st.secrets.get(key, default)
    except FileNotFoundError:
        return default

class Config:
    DEEPSEEK_API_KEY = get_secret("DEEPSEEK_API_KEY")
    GLM_API_KEY = get_secret("GLM_API_KEY")
    QWEN_API_KEY = get_secret("QWEN_API_KEY")
    TAVILY_API_KEY = get_secret("TAVILY_API_KEY")
    
    SYSTEM_PROMPT = get_secret("SYSTEM_PROMPT")
    DEEPSEEK_PROMPT = get_secret("DEEPSEEK_PROMPT")
    GLM_PROMPT = get_secret("GLM_PROMPT")
    QWEN_PROMPT = get_secret("QWEN_PROMPT")
    EVALUATOR_PROMPT = get_secret("EVALUATOR_PROMPT")

config = Config()

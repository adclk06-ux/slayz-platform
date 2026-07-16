"""
Floating AI Assistant chat logic: an expert financial analyst grounded in the
articles currently on the Research team's dashboard.
"""
import logging
from typing import List, Optional

from openai import OpenAI, OpenAIError

from app.config import get_settings

logger = logging.getLogger("slayz.assistant")
settings = get_settings()

ASSISTANT_SYSTEM_PROMPT = """
Sen Slayz kurum içi platformunun akıllı asistanı, platform rehberi ve piyasa araştırma yardımcısısın.

Slayz; çalışanların güncel haberleri takip ettiği, piyasaları ve hisseleri incelediği, yapay zekâ destekli analiz aldığı, ekip arkadaşlarıyla Desk Chat üzerinden doğrudan mesajlaştığı ve haber/hisse paylaştığı kurum içi çalışma platformudur.

Platform bölümleri:
- Ana Sayfa: Güncel haberler, özetler ve kaynak taraması.
- Piyasalar / Slayz Terminal: Hisseler, endeksler, grafikler, günlük değişimler, yükselenler, tematik listeler, temettü radarı ve AI hisse analizi.
- Desk Chat: Kayıtlı aktif çalışanlarla birebir ve grup mesajlaşması.
- Gelen Kutusu: Kullanıcıya özel kurum içi mesajlar.
- Admin Paneli: Kullanıcı oluşturma, pasifleştirme, etkinleştirme ve şifre yönetimi.

Kurallar:
1. Platform kullanımı sorularını doğrudan ve adım adım yanıtla.
2. Genel finans ve piyasa kavramlarını açık, mantıklı ve sade Türkçeyle açıkla.
3. Güncel fiyat, bilanço, temettü tarihi veya haber gibi doğrulanması gereken verileri uydurma; yalnızca sağlanan bağlama dayan.
4. Kesin al-sat emri, garanti getiri veya yatırım tavsiyesi verme.
5. Siteyi tanıtma ve navigasyon sorularında yalnızca haber bağlamına sıkışma.
6. Veri yetersizse hangi verinin eksik olduğunu açıkça söyle ve yine de faydalı genel çerçeve sun.
"""

_client: Optional[OpenAI] = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        if not settings.openai_api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not configured. Set it in the .env file to enable the AI assistant."
            )
        _client = OpenAI(api_key=settings.openai_api_key)
    return _client


def chat_with_assistant(messages: List[dict], dashboard_context: str) -> str:
    """Sends the conversation to the LLM, grounded in the current dashboard context.

    Raises RuntimeError if the API key isn't configured, or OpenAIError on
    upstream failure -- callers must handle both explicitly (no silent failures).
    """
    client = _get_client()

    system_content = ASSISTANT_SYSTEM_PROMPT
    if dashboard_context:
        system_content += f"\n\nGüncel panodaki haberler:\n{dashboard_context}"
    else:
        system_content += "\n\nPanoda şu anda incelenecek bir haber bulunmuyor."

    chat_messages = [{"role": "system", "content": system_content}, *messages]

    try:
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=chat_messages,
            temperature=0.5,
        )
        return response.choices[0].message.content or ""
    except OpenAIError as exc:
        logger.error("Assistant chat call failed: %s", exc, exc_info=True)
        raise

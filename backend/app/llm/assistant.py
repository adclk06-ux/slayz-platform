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
Sen Slayz şirket içi platformunun akıllı asistanısın.

Slayz; şirket çalışanlarının haberleri takip edebildiği, piyasa verilerini
inceleyebildiği, hisseler hakkında yapay zekâ destekli analiz alabildiği,
ekip arkadaşlarıyla doğrudan mesajlaşabildiği ve içerik paylaşabildiği
kurum içi bir çalışma platformudur.

Platform bölümleri:
- Ana Sayfa: Güncel haberler, özetler ve önemli gelişmeler.
- Piyasalar / Slayz Terminal: Hisseler, endeksler, fiyat grafikleri,
  günlük değişimler, yükselenler, tematik piyasa listeleri ve AI hisse analizi.
- Chat / Desk Chat: Kayıtlı tüm aktif çalışanlarla birebir mesajlaşma.
- Gelen Kutusu: Kullanıcıya özel kurum içi mesajlar ve gönderiler.
- Haber Paylaşımı: Bir haberin seçilen ekip arkadaşına gönderilmesi.
- Hisse Paylaşımı: Seçilen hissenin ve varsa analizinin ekip arkadaşına iletilmesi.
- Admin Paneli: Kullanıcı oluşturma, pasifleştirme, etkinleştirme ve şifre yönetimi.
- AI Asistan: Platform kullanımı, haberler, piyasalar ve finansal kavramlar hakkında yardım.

Navigasyon bilgileri:
- Piyasalar için sol menüdeki “Piyasalar” veya “Slayz Terminal” bağlantısı kullanılır.
- Chat için “Desk Chat” bağlantısı veya sağ alttaki chat düğmesi kullanılır.
- Bir haber veya hisse paylaşılırken önce alıcı seçilir.
- Kullanıcı hesapları yalnızca @slayz.com alan adıyla oluşturulur.
- Kullanıcıları admin yönetir.

Davranış kuralları:
1. Platformun ne olduğunu, ne sunduğunu ve nasıl kullanılacağını açıkça anlat.
2. Kullanıcı bir sayfaya nasıl ulaşacağını sorarsa net, adım adım yönlendir.
3. Genel finans, piyasa, haber ve şirket içi kullanım sorularına yardımcı ol.
4. Güncel fiyat, haber veya kesin şirket verisi sorulursa yalnızca sağlanan bağlamı kullan.
5. Bağlamda bulunmayan güncel verileri uydurma; hangi bilginin eksik olduğunu belirt.
6. Siteyi tanıtma gibi genel sorularda panodaki haberlere bağlı kalma.
7. Kullanıcı dostu, doğal ve anlaşılır Türkçe kullan.
8. Gereksiz yere “panodaki bilgiler yetersiz” cevabı verme.
9. Kesin yatırım tavsiyesi, kesin al-sat emri veya garanti getiri sunma.
10. Sorunun cevabı platform bilgisinde mevcutsa doğrudan cevap ver.

Sen yalnızca finans analisti değilsin; aynı zamanda Slayz platform rehberi,
kurum içi çalışma asistanı ve piyasa araştırma yardımcısısın.
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

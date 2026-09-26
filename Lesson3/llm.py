import os
import sys
import time
import logging

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("llm")
# чужі логи (http-запити і т.п.) не потрібні
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("google_genai").setLevel(logging.ERROR)

# версію моделі фіксую явно, щоб не змінилась поведінка без мого відома
MODELS = {
    "google": "gemini-3.5-flash-lite",
    "openai": "gpt-4.1-mini",
}

# ціна в $ за 1М токенів (вхід, вихід), брав з офіційних сторінок 26.09.2026:
# https://ai.google.dev/gemini-api/docs/pricing
# https://developers.openai.com/api/docs/pricing
PRICES = {
    "gemini-3.5-flash-lite": (0.30, 2.50),
    "gpt-4.1-mini": (0.40, 1.60),
}

KEY_NAMES = {
    "google": "GOOGLE_API_KEY",
    "openai": "OPENAI_API_KEY",
}


def get_key(provider):
    name = KEY_NAMES[provider]
    key = os.environ.get(name, "").strip()
    if not key:
        raise RuntimeError(f"Немає ключа {name} у .env")
    return key


def with_retry(fn, max_attempts=5):
    # 1 -> 2 -> 4 -> 8 сек між спробами
    # по-хорошому 400/401 повторювати немає сенсу (ключ сам не виправиться),
    # але в ДЗ retry треба показати саме на невірному ключі, тому повторюю все
    for attempt in range(max_attempts):
        try:
            return fn()
        except Exception as e:
            if attempt == max_attempts - 1:
                log.error(f"Спроба {attempt + 1}/{max_attempts} невдала: {type(e).__name__}: {str(e)[:150]}")
                raise RuntimeError(f"LLM недоступна після {max_attempts} спроб") from e
            delay = 2 ** attempt
            log.warning(f"Спроба {attempt + 1}/{max_attempts} невдала: {type(e).__name__}: {str(e)[:150]}. Повтор через {delay} c")
            time.sleep(delay)


def _call_google(prompt, system, model, max_tokens, json_mode):
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=get_key("google"))
    config = types.GenerateContentConfig(
        temperature=0,
        max_output_tokens=max_tokens,
        system_instruction=system or None,  # у google system - окреме поле в config
    )
    if json_mode:
        config.response_mime_type = "application/json"

    resp = client.models.generate_content(model=model, contents=prompt, config=config)
    usage = resp.usage_metadata
    # у gemini 3.x є "thinking", ці токени рахуються як вихідні і входять в max_output_tokens
    thoughts = usage.thoughts_token_count or 0
    finish = resp.candidates[0].finish_reason if resp.candidates else None
    return {
        "text": resp.text or "",
        "in_tokens": usage.prompt_token_count or 0,
        "out_tokens": (usage.candidates_token_count or 0) + thoughts,
        "stop_reason": getattr(finish, "name", str(finish)),
    }


def _call_openai(prompt, system, model, max_tokens, json_mode):
    from openai import OpenAI

    # max_retries=0 - щоб sdk не робив свої повтори, retry в мене свій
    client = OpenAI(api_key=get_key("openai"), max_retries=0)
    messages = []
    if system:
        messages.append({"role": "system", "content": system})  # у openai system - це повідомлення в messages
    messages.append({"role": "user", "content": prompt})

    kwargs = {}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0,
        max_tokens=max_tokens,
        **kwargs,
    )
    return {
        "text": resp.choices[0].message.content or "",
        "in_tokens": resp.usage.prompt_tokens,
        "out_tokens": resp.usage.completion_tokens,
        "stop_reason": resp.choices[0].finish_reason,
    }


CALLS = {
    "google": _call_google,
    "openai": _call_openai,
}


def llm(prompt: str, system: str = "", provider: str = "google", max_tokens: int = 1000, json_mode: bool = False) -> dict:
    """
    Один виклик моделі. Повертає словник:
    text, in_tokens, out_tokens, stop_reason, seconds, cost_usd (+ provider, model)
    """
    if provider not in CALLS:
        raise ValueError(f"Невідомий провайдер: {provider}. Є: {list(CALLS)}")
    model = MODELS[provider]

    start = time.perf_counter()
    result = with_retry(lambda: CALLS[provider](prompt, system, model, max_tokens, json_mode))
    seconds = time.perf_counter() - start  # разом з паузами retry, якщо вони були

    price_in, price_out = PRICES[model]
    cost = (result["in_tokens"] * price_in + result["out_tokens"] * price_out) / 1_000_000

    result.update({
        "provider": provider,
        "model": model,
        "seconds": round(seconds, 2),
        "cost_usd": cost,
    })

    log.info(f"{provider}/{model} | in={result['in_tokens']} out={result['out_tokens']} | "
             f"{result['stop_reason']} | {result['seconds']} c | ${cost:.6f}")
    if str(result["stop_reason"]).lower() in ("max_tokens", "length"):
        log.warning("Відповідь обрізана по max_tokens!")
    return result


def show_keys():
    # друкую тільки останні 4 символи, сам ключ не світимо
    for provider, name in KEY_NAMES.items():
        key = os.environ.get(name, "").strip()
        print(f"{name}: {'...' + key[-4:] if key else 'немає'}")


if __name__ == "__main__":
    # python llm.py                    - перевірити ключі
    # python llm.py google "питання"   - один виклик
    if len(sys.argv) < 2:
        show_keys()
    else:
        provider = sys.argv[1]
        question = sys.argv[2] if len(sys.argv) > 2 else "Одним словом: столиця України?"
        r = llm(question, system="Відповідай коротко.", provider=provider, max_tokens=300)
        print()
        print("Відповідь:", r["text"])
        print("stop_reason:", r["stop_reason"])
        print("токени in/out:", r["in_tokens"], r["out_tokens"])

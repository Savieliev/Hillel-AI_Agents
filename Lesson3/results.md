# Заняття 3 - результати

Задача: парсер вхідних повідомлень для CRM - витягнути name, company, intent, is_urgent у JSON
(промпт v2 з ДЗ 2), 5 входів, temperature=0.

Відповідь вважаю правильною, якщо це валідний JSON, name / company / is_urgent збігаються з очікуваними
(без урахування регістру і пробілів), а intent не порожній. Intent - вільний текст, тому його перевіряв очима.

## Таблиця

провайдер | модель | правильних із 5 | in tok | out tok | вартість $ | сер. час, с
----------|--------|-----------------|--------|---------|------------|------------
google | gemini-3.5-flash-lite |  |  |  |  |
openai | gpt-4.1-mini |  |  |  |  |

Вартість рахується в llm() за формулою `(in_tokens * price_in + out_tokens * price_out) / 1_000_000`.
Для Gemini в out_tokens додаю thinking-токени, бо вони оплачуються як вихідні.

## Ціни ($ за 1М токенів, станом на 26.09.2026)

модель | вхід | вихід | звідки
-------|------|-------|-------
gemini-3.5-flash-lite | 0.30 | 2.50 | https://ai.google.dev/gemini-api/docs/pricing
gpt-4.1-mini | 0.40 | 1.60 | https://developers.openai.com/api/docs/pricing
claude-haiku-4-5 | 1.00 | 5.00 | https://platform.claude.com/docs/en/about-claude/pricing

## Висновок

...

## Файли

- `llm.py` - функція llm() (google / openai / anthropic), retry 1-2-4-8 с, токени і вартість
- `run_tests.py` - прогін тестсету на провайдерах, таблиця
- `test_retry.py` - перевірка retry з невірним ключем
- `prompt.py`, `testset.json` - промпт і 5 входів з ДЗ 2
- `.env.example` - шаблон для ключів

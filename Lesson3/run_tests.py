# прогін тестсету (5 входів) через llm() на кількох провайдерах
# запуск: python run_tests.py google openai
#   без аргументів - всі провайдери, для яких є ключ у .env

import os
import sys
import json
import time

from llm import llm, MODELS, KEY_NAMES
from prompt import SYSTEM, TEMPLATE

PAUSE = 5  # сек між запитами, щоб не ловити 429 на безкоштовному тарифі


def parse_json(text):
    text = text.strip()
    # іноді модель все одно загортає в ```json ... ```
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)


def run(provider, tests):
    rows = []
    for t in tests:
        prompt = TEMPLATE.format(text=t["text"])
        try:
            r = llm(prompt, system=SYSTEM, provider=provider, max_tokens=1000, json_mode=True)
        except RuntimeError as e:
            print(f"  #{t['id']} ПОМИЛКА: {e}")
            rows.append({"id": t["id"], "ok": False, "pred": "error", "in_tokens": 0,
                         "out_tokens": 0, "cost_usd": 0, "seconds": 0})
            time.sleep(PAUSE)
            continue

        try:
            pred = parse_json(r["text"])["sentiment"]
        except (json.JSONDecodeError, KeyError, TypeError):
            pred = "не json: " + r["text"][:60]

        ok = pred == t["expected"]
        print(f"  #{t['id']} очікував={t['expected']:8} отримав={pred:8} {'OK' if ok else 'НЕ ТЕ'}")
        rows.append({"id": t["id"], "ok": ok, "pred": pred, **r})
        time.sleep(PAUSE)
    return rows


def main():
    providers = sys.argv[1:] or [p for p, k in KEY_NAMES.items() if os.environ.get(k, "").strip()]
    if not providers:
        print("Немає жодного ключа в .env")
        return

    with open("testset.json", encoding="utf-8") as f:
        tests = json.load(f)

    table = []
    for p in providers:
        print(f"\n=== {p} ({MODELS[p]}) ===")
        rows = run(p, tests)
        table.append({
            "provider": p,
            "model": MODELS[p],
            "correct": sum(r["ok"] for r in rows),
            "in": sum(r["in_tokens"] for r in rows),
            "out": sum(r["out_tokens"] for r in rows),
            "cost": sum(r["cost_usd"] for r in rows),
            "avg_s": sum(r["seconds"] for r in rows) / len(rows),
        })
        with open(f"raw_{p}.json", "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)

    lines = [
        "провайдер | модель | правильних із 5 | in tok | out tok | вартість $ | сер. час, с",
        "----------|--------|-----------------|--------|---------|------------|------------",
    ]
    for t in table:
        lines.append(f"{t['provider']} | {t['model']} | {t['correct']} | {t['in']} | {t['out']} | "
                     f"{t['cost']:.6f} | {t['avg_s']:.2f}")

    print("\n" + "\n".join(lines))
    with open("results_table.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\nТаблицю збережено в results_table.md")


if __name__ == "__main__":
    main()

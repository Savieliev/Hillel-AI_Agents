# перевірка retry: підставляю навмисно невірний ключ і дивлюсь спроби в консолі
# запуск: python test_retry.py  (або python test_retry.py openai)

import os
import sys

import llm as llm_module

provider = sys.argv[1] if len(sys.argv) > 1 else "google"
os.environ[llm_module.KEY_NAMES[provider]] = "wrong-key-12345"

llm_module.llm("Привіт", provider=provider, max_tokens=50)

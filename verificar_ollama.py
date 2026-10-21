import os
import time

from dotenv import load_dotenv
from langchain_ollama import ChatOllama, OllamaEmbeddings

load_dotenv(override=True)
modelo_emb = os.getenv("EMBEDDING_MODEL")
modelo_llm = os.getenv("LLM_MODEL")

print(f"1) Probando embeddings con {modelo_emb}...", flush=True)
t = time.perf_counter()
vector = OllamaEmbeddings(model=modelo_emb).embed_query("Tolvak es una plataforma de mensajería")
print(f"   OK: {len(vector)} dimensiones ({time.perf_counter() - t:.1f} s)", flush=True)

print(f"2) Probando {modelo_llm}...", flush=True)
t = time.perf_counter()
llm = ChatOllama(model=modelo_llm, num_predict=60)
print("   respuesta: ", end="", flush=True)
for trozo in llm.stream("Responde solo con la palabra: hola"):
    print(trozo.content, end="", flush=True)
print(f"\n   OK ({time.perf_counter() - t:.1f} s)")
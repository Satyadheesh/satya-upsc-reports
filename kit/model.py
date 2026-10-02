"""Gemma 4 12B (GGUF, CPU) through llama.cpp — the same model the UPSC service uses."""
import json
import os

MODEL_REPO = os.environ.get("KIT_MODEL_REPO", "unsloth/gemma-4-12b-it-GGUF")
MODEL_FILE = os.environ.get("KIT_MODEL_FILE", "gemma-4-12b-it-Q4_K_M.gguf")
MODEL_NAME = MODEL_FILE.rsplit(".", 1)[0]


def download(model_dir="models"):
    from huggingface_hub import hf_hub_download
    os.makedirs(model_dir, exist_ok=True)
    path = os.path.join(model_dir, MODEL_FILE)
    if not os.path.exists(path):
        hf_hub_download(repo_id=MODEL_REPO, filename=MODEL_FILE, local_dir=model_dir)
    return path


class Model:
    def __init__(self, path, n_ctx=4096):
        from llama_cpp import Llama
        self.llm = Llama(model_path=path, n_ctx=n_ctx, n_gpu_layers=int(os.environ.get("KIT_GPU_LAYERS", "-1")),
                         verbose=False)

    def json(self, system, user, schema, temperature=0.2, max_tokens=900):
        out = self.llm.create_chat_completion(
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            response_format={"type": "json_object", "schema": schema},
            temperature=temperature, max_tokens=max_tokens,
        )
        return json.loads(out["choices"][0]["message"]["content"])

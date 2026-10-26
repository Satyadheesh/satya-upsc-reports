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


def fix_detokenize(llm):
    """llama-cpp-python 0.3.36 decodes each token into a 32-byte buffer; a longer piece (one token for a long Hindi word:
    " मुख्यमंत्री" is 34 bytes, "प्रधानमंत्री" 36, "उपमुख्यमंत्री" 39) makes llama_token_to_piece return the needed size as
    a negative number, and the library then keeps b"" - the word silently disappears from every output (found 26 Oct
    2026). Replace the model's detokenize with one that retries with a big enough buffer."""
    import ctypes
    import llama_cpp as lc
    model = llm._model

    def detokenize(tokens, special=False):
        out, size = b"", 64
        for t in tokens:
            buf = (ctypes.c_char * size)()
            n = lc.llama_token_to_piece(model.vocab, lc.llama_token(t), buf, size, 0, special)
            if n < 0:
                size = -n + 8
                buf = (ctypes.c_char * size)()
                n = lc.llama_token_to_piece(model.vocab, lc.llama_token(t), buf, size, 0, special)
            out += bytes(buf[:max(n, 0)])
        if tokens and tokens[0] == model.token_bos() and out[:1] == b" ":
            out = out[1:]
        return out

    model.detokenize = detokenize


class Model:
    def __init__(self, path, n_ctx=4096, fix_long_tokens=False):
        from llama_cpp import Llama
        self.llm = Llama(model_path=path, n_ctx=n_ctx, n_gpu_layers=int(os.environ.get("KIT_GPU_LAYERS", "-1")),
                         verbose=False)
        if fix_long_tokens:   # opt-in per service (reels first, 26 Oct 2026); see fix_detokenize
            fix_detokenize(self.llm)

    def json(self, system, user, schema, temperature=0.2, max_tokens=900):
        out = self.llm.create_chat_completion(
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            response_format={"type": "json_object", "schema": schema},
            temperature=temperature, max_tokens=max_tokens,
        )
        return json.loads(out["choices"][0]["message"]["content"])

    def text(self, system, user, temperature=0.3, max_tokens=900):
        """Plain text, no JSON grammar (Gemma's Hindi through the grammar dropped words; reels, 26 Oct 2026)."""
        out = self.llm.create_chat_completion(
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=temperature, max_tokens=max_tokens,
        )
        return out["choices"][0]["message"]["content"] or ""

    def chat(self, messages, schema, temperature=0.2, max_tokens=350):
        out = self.llm.create_chat_completion(
            messages=messages,
            response_format={"type": "json_object", "schema": schema},
            temperature=temperature, max_tokens=max_tokens,
        )
        return json.loads(out["choices"][0]["message"]["content"])

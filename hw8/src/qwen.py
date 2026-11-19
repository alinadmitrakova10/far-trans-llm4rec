"""Frozen embedding inference, deliberately lazy-imported and explicitly invoked."""
import importlib.metadata
import platform
import time

MODEL_ID = 'Qwen/Qwen3-Embedding-0.6B'
REVISION = '97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3'


def tokenizer():
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained(MODEL_ID, revision=REVISION,
                                         padding_side='left', trust_remote_code=False)


def embed(texts, tok, batch_size=8, device='cuda'):
    import numpy as np
    import torch
    from transformers import AutoModel
    if device == 'cuda' and not torch.cuda.is_available():
        raise RuntimeError('CUDA requested but unavailable; select CPU explicitly')
    torch.manual_seed(42)
    torch.use_deterministic_algorithms(True)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    dtype = torch.float16 if device == 'cuda' else torch.float32
    start = time.perf_counter()
    model = AutoModel.from_pretrained(MODEL_ID, revision=REVISION, torch_dtype=dtype,
                                     attn_implementation='eager', trust_remote_code=False)
    model.to(device).eval().requires_grad_(False)
    assert model.config.hidden_size == 1024
    load_seconds = time.perf_counter() - start
    unique = sorted(set(texts))
    cache, failures = {}, []
    if device == 'cuda':
        torch.cuda.synchronize()
        torch.cuda.reset_peak_memory_stats()
    start = time.perf_counter()
    with torch.inference_mode():
        for offset in range(0, len(unique), batch_size):
            batch = unique[offset:offset + batch_size]
            try:
                inputs = tok(batch, padding=True, truncation=False, return_tensors='pt')
                if inputs['input_ids'].shape[1] > 512:
                    raise ValueError('Shared truncation was not applied')
                inputs = {k: v.to(device) for k, v in inputs.items()}
                hidden = model(**inputs).last_hidden_state
                # Left padding: last nonpadding token is always the final column.
                pooled = hidden[:, -1, :].float()
                pooled = torch.nn.functional.normalize(pooled, p=2, dim=1)
                values = pooled.cpu().numpy()
                for text, value in zip(batch, values):
                    if not np.isfinite(value).all() or np.linalg.norm(value) == 0:
                        raise ValueError('Nonfinite or zero embedding')
                    cache[text] = value
            except (RuntimeError, ValueError) as error:
                # Preserve all users: failed profiles are zero vectors, common scorer fallback.
                for text in batch:
                    cache[text] = np.zeros(model.config.hidden_size, dtype=np.float32)
                    failures.append(dict(text_sha256=__import__('hashlib').sha256(text.encode()).hexdigest(),
                                         error=str(error)))
    if device == 'cuda':
        torch.cuda.synchronize()
    seconds = time.perf_counter() - start
    metadata = dict(model_id=MODEL_ID, revision=REVISION, frozen=True,
                    embedding_dimension=1024, seed=42, deterministic_algorithms=True, tf32=False,
                    pooling='last non-padding token; left padding', normalization='L2 float32',
                    precision=str(dtype), device=device, batch_size=batch_size,
                    attention='eager', max_tokens=512, unique_profiles=len(unique),
                    inference_seconds=seconds, model_load_seconds=load_seconds,
                    inference_scope='tokenization + forward + pooling + normalization + CPU transfer; unique profiles',
                    failures=failures, python=platform.python_version(),
                    libraries={p: importlib.metadata.version(p) for p in
                               ('torch', 'transformers', 'tokenizers', 'numpy', 'huggingface-hub', 'safetensors')},
                    hardware=torch.cuda.get_device_name() if device == 'cuda' else platform.processor(),
                    peak_cuda_bytes=torch.cuda.max_memory_allocated() if device == 'cuda' else None)
    return np.stack([cache[t] for t in texts]), metadata

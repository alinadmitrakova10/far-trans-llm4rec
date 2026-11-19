"""One exact cosine user-kNN implementation for both encoders; no truth input."""
import numpy as np

NEIGHBOR_K = 20  # A-priori engineering choice, not tuned on June purchases.


def recommend(vectors, neighbor_users, evaluation_users, history, catalog, popularity):
    vectors = np.asarray(vectors, dtype=np.float32)
    if vectors.ndim != 2 or len(vectors) != len(neighbor_users):
        raise ValueError('Wrong embedding shape')
    valid = np.isfinite(vectors).all(axis=1)
    norms = np.linalg.norm(np.where(np.isfinite(vectors), vectors, 0), axis=1)
    valid &= norms > 0
    normalized = np.zeros_like(vectors)
    normalized[valid] = vectors[valid] / norms[valid, None]
    positions = {uid: i for i, uid in enumerate(neighbor_users)}
    catalog = sorted(catalog)
    columns = {isin: i for i, isin in enumerate(catalog)}
    # Binary matrix shared across branches, regardless of representation truncation.
    purchases = np.zeros((len(neighbor_users), len(catalog)), dtype=np.float32)
    for r, uid in enumerate(neighbor_users):
        for isin in history[uid]:
            purchases[r, columns[isin]] = 1
    predictions, diagnostics = {}, {}
    for uid in evaluation_users:
        row = positions[uid]
        cosine = normalized @ normalized[row]
        cosine[~valid] = -np.inf
        cosine[row] = -np.inf
        # neighbor_users sorted by ID, stable sorting resolves equal similarity by ID.
        neighbors = np.argsort(-cosine, kind='stable')[:NEIGHBOR_K]
        neighbors = neighbors[cosine[neighbors] > 0]
        scores = (np.maximum(cosine[neighbors], 0) @ purchases[neighbors]
                  if valid[row] and len(neighbors) else np.zeros(len(catalog)))
        fallback = not bool(np.any(scores > 0))
        if fallback:
            scores = np.array([popularity[i] for i in catalog], dtype=np.float64)
        ranked = np.argsort(-scores, kind='stable')[:10]
        predictions[uid] = [catalog[i] for i in ranked]
        diagnostics[uid] = dict(fallback=fallback, invalid_query=not bool(valid[row]),
                                neighbors=[neighbor_users[i] for i in neighbors],
                                similarities=[float(cosine[i]) for i in neighbors])
    return predictions, dict(users=diagnostics, invalid_embedding_rows=int((~valid).sum()))

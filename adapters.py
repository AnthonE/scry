"""
adapters.py — wire memory-shield into any agent framework in one line.

Coverage for the three named ecosystems (and anything else):
  - elizaOS    -> native TypeScript plugin (../../packages/eliza-plugin) — Shield + memory contract
  - OpenClaw / moltbot -> chromadb-memory: wrap the chromadb query with `wrap_retriever` (below)
  - Hermes (NousResearch/hermes-agent) -> persistent/episodic memory: wrap recall the same way

The core idea: every framework does `retrieve(query) -> items -> act`. You insert `Shield.defend`
between retrieve and act. `wrap_retriever` does that for any retriever; the `*_to_items` helpers map
each framework's result shape into the {claim, source, content} the Shield expects.
"""
from memory_shield import Shield, Result

def wrap_retriever(retrieve, shield: Shield, to_items=None):
    """Turn any retriever `retrieve(query) -> raw` into a hardened one returning a defended Result."""
    def hardened(query) -> Result:
        raw = retrieve(query)
        items = to_items(raw) if to_items else raw
        return shield.defend(items)
    return hardened

# --- OpenClaw / moltbot: chromadb-memory --------------------------------------------------------
def chromadb_to_items(results, claim_key="answer"):
    """Map a chromadb `.query(...)` result into shield items. Source comes from each doc's metadata
    (`source`); the claim is metadata[claim_key] if present, else the document text."""
    docs  = (results.get("documents")  or [[]])[0]
    metas = (results.get("metadatas")  or [[]])[0]
    items = []
    for doc, meta in zip(docs, metas):
        meta = meta or {}
        items.append({"content": doc, "claim": meta.get(claim_key, doc), "source": meta.get("source", "unknown")})
    return items

# --- Hermes (NousResearch/hermes-agent): persistent / episodic memory ---------------------------
def hermes_memories_to_items(memories):
    """Map Hermes recalled memory entries -> shield items. Each entry is expected to carry a `source`
    (who/what produced it) and either a `claim` or `text`. Episodic entries (learned-from-failure) get
    `source='self:episodic'` — which should NOT be in your trusted set, so the agent corroborates them
    rather than obeying them blindly (self-improving memory is exactly the poisoning/drift surface)."""
    out = []
    for m in memories:
        src = m.get("source") or ("self:episodic" if m.get("kind") == "episodic" else "unknown")
        out.append({"content": m.get("text", ""), "claim": m.get("claim", m.get("text", "")), "source": src})
    return out

if __name__ == "__main__":
    shield = Shield(trusted_sources={"wiki", "user", "tool:calculator"})

    # simulate a chromadb result: 3 trusted say paris, 4 spoofed say lyon
    fake_chroma = {"documents": [["paris...", "paris...", "paris...", "lyon...", "lyon...", "lyon...", "lyon..."]],
                   "metadatas": [[{"source": "wiki", "answer": "paris"}, {"source": "tool:calculator", "answer": "paris"},
                                  {"source": "user", "answer": "paris"}] + [{"source": f"spoof{i}", "answer": "lyon"} for i in range(4)]]}
    harden = wrap_retriever(lambda q: fake_chroma, shield, chromadb_to_items)
    print("OpenClaw/moltbot (chromadb) — defended answer:", harden("capital of france").answer, "(naive would say: lyon)")

    # simulate Hermes episodic recall: an episodic 'lesson' tries to override a trusted fact
    hermes_mem = [{"text": "", "claim": "paris", "source": "user", "kind": "fact"},
                  {"text": "", "claim": "lyon", "kind": "episodic"}]   # self-learned, untrusted -> can't override
    harden_h = wrap_retriever(lambda q: hermes_mem, shield, hermes_memories_to_items)
    print("Hermes (episodic memory)     — defended answer:", harden_h("capital of france").answer, "(episodic self-claim can't override a trusted source)")
    print("\nOne line — `wrap_retriever(your_retrieve, shield, mapper)` — covers all three. The TS plugin")
    print("does the same natively for elizaOS. Same shield, same contract, every stack.")

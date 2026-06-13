# FIELD-TEST — wiring memory-shield into a live agent (the 30-min-per-stack checklist)

Everything here is *validated logic*; this is the mechanical wire-in against a *running* agent. For each
framework: (1) confirm the memory result-shape so the mapper is right, (2) set trusted sources, (3) put
the **contract** guard on sensitive actions (the part that stops the money exploit), (4) run the red-team
as your regression test. Success = `redteam` exits 0 and your sensitive actions refuse memory-only authority.

## Pre-flight (any stack)
- Python side is **pure stdlib** — no deps. `python redteam.py` (from the repo root) should print
  `shielded survived 3/3` and exit 0. (elizaOS: `npm run redteam` in the separate `@moreright/eliza-plugin` package.)
- Decide your **trusted sources** = the principals you actually authenticate (e.g. the agent owner's
  verified user id, your own tools, a canonical KB). Everything else is untrusted by default.

## 1. elizaOS  (native plugin — already wired)
1. Add to `character.json`: `"plugins": ["@moreright/eliza-plugin"]`, and
   `"settings": { "MORERIGHT_TRUSTED_SOURCES": "<owner-userId>,<your-tool-ids>" }`.
2. **Confirm the result shape:** the `memoryIntegrity` provider reads `state.recentMessagesData` (Memory[])
   and uses `m.userId` as the source. Verify your elizaOS version populates that (standard builds do).
   If your memories carry a custom author field, change `m.userId` in `providers/memoryIntegrity.ts`.
3. **Put the contract on sensitive actions (DO THIS — it's the money defense):** in any action handler
   that moves value / calls a tool with side-effects, gate it:
   ```ts
   import { authorizeAction } from '@moreright/eliza-plugin';
   const ok = authorizeAction({
     live: { text: (message.content as any).text, source: message.userId ?? '', role: 'live_instruction' },
     trusted: new Set((runtime.getSetting('MORERIGHT_TRUSTED_SOURCES')||'').split(',')),
   });
   if (!ok.authorized) { await callback({ text: `refused: ${ok.reason}` }); return false; }
   ```
   (The plugin can't auto-wrap *your* actions — this guard is the one line that makes memory-injected
   commands inert.)
4. Run `npm run redteam`. Watch the naive column get HIJACKED, shielded SAFE.

## 2. OpenClaw / moltbot  (chromadb-memory)
1. **Confirm the result shape + the critical prerequisite:** your memories MUST be stored with a source in
   metadata — `collection.add(documents=[...], metadatas=[{"source": "<who>"}], ...)`. Without it every
   source is `"unknown"` and trust-weighting can't work. *This is the #1 field-test fix.*
2. Wrap the retrieval:
   ```python
   from memory_shield import Shield
   from adapters import wrap_retriever, chromadb_to_items
   shield = Shield(trusted_sources={"<owner>", "tool:...", "kb"})
   recall = wrap_retriever(lambda q: collection.query(query_texts=[q], n_results=8), shield, chromadb_to_items)
   result = recall(user_query)          # result.answer / result.confident / result.flags
   ```
3. **Contract on side-effecting MCP tools / actions:** before executing one, require a live authenticated
   instruction (the OpenClaw message author in your trusted set) — `authorize_action(...)` in `redteam.py`
   is the reference. Stored memory never authorizes.
4. `python redteam.py`.

## 3. Hermes  (NousResearch/hermes-agent — persistent/episodic memory)
1. **Confirm the recall shape:** find Hermes's recall call and inspect one returned entry. Map its fields in
   `hermes_memories_to_items` (defaults assume `text`, optional `claim`, `source`, `kind`). Mark *episodic*
   (self-learned-from-failure) entries `kind="episodic"` → they map to `source="self:episodic"`, which you
   should **leave out of the trusted set** so the self-improving loop can't drift itself.
2. Wrap recall:
   ```python
   recall = wrap_retriever(hermes.memory.recall, shield, hermes_memories_to_items)
   ```
3. **Contract on tool-calls:** Hermes is agentic with tool use — gate any consequential tool call on a live
   authenticated user instruction, not on recalled memory.
4. `python redteam.py`.

## What "passing in the field" means
- `redteam` exits 0 on every stack (naive HIJACKED, shielded SAFE on all 3 classes).
- A sensitive action, fed a memory-planted "authorization," **refuses** (the contract).
- The provider/evaluator fire on a planted flood / injection in your real logs.
- Honest limits to remember: an attacker who controls a *majority of trusted sources* still wins
  (coverage limit); un-verifiable beliefs can only be held low-confidence, not made correct. Set your
  trusted set tightly and give the shield a `verify=` for anything checkable (math, canonical lookups).

Report back what the result-shapes actually were on your deployments — that's the last unknown, and it's
the only thing that turns "validated logic" into "drop-in on your stack."

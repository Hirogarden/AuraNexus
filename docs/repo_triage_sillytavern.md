# SillyTavern Ecosystem Triage (New Candidates)

## Tier A — High Value (Do These)
- ✅ SillyTavern/SillyTavern — **ALREADY IN ROADMAP** (Section 2, reference only due to AGPL)
- RossAscends/STMP (multiplayer/raid logic, host/guest roles, API routing) — **NEW**
- SillyTavern/SillyTavern-Content (templates, lore/worldbooks, assets; MIT) — **NEW**
- ✅ LostRuins/koboldcpp — **ALREADY IN ROADMAP** (Section 1, backend integration)

## Tier B — Strong Value (After Tier A)
- ✅ SillyTavern/SillyTavern-Launcher — **ALREADY IN QUEUE** (Repo #7, Tier 2)
- ✅ SillyTavern/SillyTavern-Docs (official docs; patterns and configuration) — **SECTION 32 COMPLETE**
- ✅ SillyTavern/SillyTavern-Extras — **ALREADY IN QUEUE** (Repo #2, Tier 1 - TTS/RAG bridge)
- ✅ SillyTavern/SillyTavern-WebSearch-Selenium (web browsing add-on patterns) — **SECTION 33 COMPLETE**
- SillyTavern/SillyTavern-Fandom-Scraper (RAG ingest patterns for wikis) — **NEW**
- SillyTavern/SillyTavern-EdgeTTS-Plugin (TTS plugin patterns) — **NEW** → **⚠️ FLAG: REFERENCE DURING VOICE/TTS IMPLEMENTATION PHASE**
- SillyTavern/SillyTavern-YouTube-Videos-Server (yt-dlp extraction server plugin) — **NEW**

## Tier C — Targeted/Niche (Do if time/need)
- RossAscends/ST-ClickToCloseEdits (UI micro-interaction plugin) — **NEW**
- RossAscends/ST-TCReasoningProfile (API profile swapping for reasoning) — **NEW**
- RossAscends/ST-CharPanelLongPress (long-press gestures plugin) — **NEW**
- SillyTavern/Plugin-WebpackTemplate (reference for plugin build setup) — **NEW**
- SillyTavern/SillyTavern-Office-Parser (document ingestion plugin) — **NEW**
- SillyTavern/SillyTavern-YouTube-Videos-Client (if present; pair with server) — **NEW**
- SillyTavern/SillyTavern-WebSearch-* variants (browsing helpers beyond Selenium) — **NEW**
- ✅ SillyTavern/Extension-VRM — **ALREADY IN QUEUE** (Repo #14, Tier 3 - 3D avatars)

## Tier D — Legacy/Reference (Skim only)
- gnurro/AIDscripts (legacy AI Dungeon scripts; action handling references) — **NEW** (but overlaps with AI Dungeon 2 Section 29)
- Cohee1207 misc small repos (need specific picks; low incremental value without target) — **NEW**
- LostRuins/lite.koboldai.net (light UI; reference) — **NEW**
- Other personal forks/templates across orgs — **NEW**

## Tier E — Likely Low Value for AuraNexus
- Non-AI utility repos in these accounts (generic tooling, non-LLM demos)
- Assets-only repos duplicated elsewhere

## Notes
- Licensing: SillyTavern core/plugins are AGPL; content repo is MIT; koboldcpp is AGPLv3.
- Focus first on Tier A to harvest patterns; Tier B for integrations; Tier C for plugin examples; Tier D skim for ideas; Tier E ignore.

════════════════════════════════════════════════════════════════
  SPS Browser — Local AI Models Folder  (V33)
════════════════════════════════════════════════════════════════

HOW IT WORKS
────────────
SPS AI V33 runs 100% on YOUR computer. No data is ever sent to
any server (unless you say yes to a web search). The AI model
files (.gguf) live in THIS folder.

ONLY ONE MODEL IS IN RAM AT A TIME — SPS swaps automatically.

────────────────────────────────────────────────────────────────
  4 MODES — choose from the bar above the message box
────────────────────────────────────────────────────────────────

💬 CHAT  — Everyday questions, explanations, summaries, links.
            Can search the web when a question needs fresh info.
            Suggested models: TinyLlama, Qwen2, Gemma 2, Phi-3.

🤖 AGENT — Does real work in a private sandbox: writes & runs
            Python code, makes files (you get a Save button),
            reads your real files and folders (asks first),
            searches the web, opens pages, and tries again
            automatically until it succeeds.
            Best model: Qwen2.5-Coder 3B (or Phi-3).

🧠 THINK  — Shows its full chain of thought, then the answer.
            Great for maths, logic, plans, hard comparisons.
            Best model: DeepSeek-R1 1.5B.

⚡ SPECIAL — Think + Agent in one:
            Step 1 (DeepSeek-R1): thinks and writes a plan.
            Step 2 (Qwen-Coder): follows the plan, does the
                    work, uses tools, retries until it works.
            Files appear in the chat as download cards.

────────────────────────────────────────────────────────────────
  RECOMMENDED MODEL FILES
────────────────────────────────────────────────────────────────

① TinyLlama 1.1B ⚡  (Chat)  ~800 MB file, ~700 MB RAM
   tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf
   https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF

② Qwen2 1.5B 🚀  (Chat)  ~1 GB file, ~900 MB RAM
   qwen2-1_5b-instruct-q4_k_m.gguf
   https://huggingface.co/Qwen/Qwen2-1.5B-Instruct-GGUF

③ Gemma 2 2B 🧠  (Chat)  ~1.6 GB file, ~1.5 GB RAM
   gemma-2-2b-it-Q4_K_M.gguf
   https://huggingface.co/bartowski/gemma-2-2b-it-GGUF

④ Phi-3 Mini 3.8B ⭐  (Chat + Agent)  ~2.4 GB file, ~2.3 GB RAM
   Phi-3-mini-4k-instruct-Q4_K_M.gguf
   https://huggingface.co/bartowski/Phi-3-mini-4k-instruct-GGUF

⑤ Qwen2.5-Coder 3B 🛠️  (Agent + Special step 2)  ~3.3 GB, ~3.6 GB RAM
   qwen2.5-coder-3b-instruct-q8_0.gguf
   https://huggingface.co/Qwen/Qwen2.5-Coder-3B-Instruct-GGUF

⑥ DeepSeek-R1 1.5B 🧠  (Think + Special step 1)  ~1.9 GB, ~2 GB RAM
   DeepSeek-R1-Distill-Qwen-1.5B-Q8_0.gguf
   https://huggingface.co/bartowski/DeepSeek-R1-Distill-Qwen-1.5B-GGUF

TIP  Start with ① or ② if your PC has less than 4 GB RAM.
     For Agent and Special you need at least 4 GB free RAM.
     For the full SPS Special experience (models ⑤ + ⑥) you
     need about 6 GB of free RAM.

HOW TO INSTALL
──────────────
1. Download the .gguf file(s) you want.
2. Copy them into THIS folder:
       <browser folder>\local_ai\models\
3. Open SPS Browser, click 🤖, open the model menu
   (the button showing the model name) → Re-scan.

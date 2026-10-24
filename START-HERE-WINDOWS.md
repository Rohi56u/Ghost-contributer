# Kartik — apne installed Ollama models ke saath setup

Ye tumhare **The Ghost Contributor** project ka full editable source package hai. Current release **0.2.1** hai; exact evidence quoting ka prompt fix included hai. Version 0.2.0 mein installed-model selector aur real-model setup wizard add hua hai. Tumhare laptop ke models yahan se dekh nahi sakta; setup tumhare laptop par unki actual list read karega. Saaton models dobara download karne ki zaroorat nahi. Ek run mein tumhara selected model use hota hai.

Implemented flow: registered Git repo → documentation gap → local Ollama → evidence + validated diff → approval → separate `ghost/…` branch commit. Current edit scope missing Python docstrings aur explicitly empty marked Markdown sections hai. Broader languages, arbitrary existing-doc rewrites aur automatic PR creation roadmap mein hain. **Complete source of the implemented MVP** diya hai; every PRD feature complete hone ka claim nahi.

## Easy Windows setup

### 1. ZIP extract karo

`ghost-contributor` folder ko normal local folder mein extract karo, example `C:\Projects\ghost-contributor`.

Required: Git for Windows, Python 3.11/3.12/3.13, aur tumhara existing Ollama. Python 3.12 locally tested hai. First Python dependency install ke liye Internet chahiye. Model weights included nahi hain, aur setup unhe download nahi karta.

### 2. Existing Ollama ko local-only mode mein start karo

Tray mein Ollama already chal raha ho toh **Quit Ollama** karo. Phir **`start-ollama-local.bat`** double-click karo. Is terminal ko khula rehne do.

Ye existing `ollama serve` ko `OLLAMA_NO_CLOUD=1` ke saath chalata hai. Model files ko download/delete nahi karta. Custom `OLLAMA_MODELS` use karte ho toh same user/environment se launcher chalao; model-directory setting preserved rahegi.

“Address already in use” ka matlab pehle wala server chal raha hai. Use tray se Quit karke retry karo. Script existing processes ko force-stop nahi karti.

Alternative: apne existing Ollama service mein cloud disabled configure karke restart karo. Sirf Ghost ke terminal mein variable set karne se pehle se running Ollama server reconfigure nahi hota. [Official Ollama instructions](https://docs.ollama.com/faq#how-do-i-disable-ollamas-cloud-features).

### 3. First-time setup

**`setup-windows.bat`** double-click karo. Ye `.venv` banayega, Python package install karega, phir wizard kholega:

1. Installed models ki numbered list mein se coding/instruction model choose karo. Embedding-only models prose generate nahi karte; cloud models local selection se exclude honge.
2. Ollama local-only mode mein restart kiya hai toh confirmation par `y` enter karo.
3. Apne **clean local Git repository** ka full path paste karo. Pehle test karna hai toh **Enter** dabao: separate sample Git repo banega.
4. Suggested repository name ke liye Enter dabao.

End mein dashboard start hoga. Terminal ka **poora URL**, `#token=…` samet, browser mein open karo. Default address `http://127.0.0.1:8765/` hai; authentication ke liye printed token bhi chahiye. URL private rakho.

### 4. Apne actual model se run

Dashboard mein repo select karo → **Find a small improvement** click karo. Ye selected **real local Ollama model** call karega. First model load slow ho sakta hai; wizard timeout 180 seconds rakhta hai.

Successful output mein model name, rationale, evidence aur diff dikhenge. Invalid output par app safe stop karega; fixed text ko actual inference ki tarah substitute nahi karta.

Diff read karo → **Approve local commit** → confirm. Generated change dedicated `ghost/…` branch mein commit hoga. Tumhari current branch par original file unchanged dikhna expected hai.

```powershell
git -C "YOUR_REPOSITORY_PATH" branch --list "ghost/*"
git -C "YOUR_REPOSITORY_PATH" show GHOST_BRANCH_NAME
```

Actual path aur displayed topic branch name use karo. Is step mein GitHub push nahi hota.

### 5. Agli baar

Local Ollama running rakho, phir **`start-ghost.bat`** double-click karo. Model/repo selection saved rehti hai; setup dobara zaroori nahi.

## Apne doosre installed model par switch

Project folder mein PowerShell kholo:

```powershell
.\.venv\Scripts\ghost.exe models
.\.venv\Scripts\ghost.exe repo list
.\.venv\Scripts\ghost.exe policy YOUR_REPO_NAME --model "EXACT_INSTALLED_MODEL_NAME" --timeout 180
.\.venv\Scripts\ghost.exe doctor --repo YOUR_REPO_NAME
```

Exact name `ghost models` / `ollama list` se copy karo, including tag if shown. Repo name registered alias hai, folder path nahi.

Model switch policy badalta hai; old pending proposal stale ho jayega. Usse Reject karo. Same base commit par rejected target intentionally suppress hota hai. Models compare karne ke liye wizard se **naya isolated sample** banao, ya repo ka next eligible target use karo. State database manually edit mat karo.

## Manual PowerShell setup

Ollama local-only mode mein start rakhkar:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\ghost.exe models
.\.venv\Scripts\ghost.exe setup
.\.venv\Scripts\ghost.exe dashboard
```

Full executable paths use karne se venv activation aur PowerShell execution-policy changes ki zaroorat nahi. `py -3.12` ko apni installed supported version ke hisaab se change kar sakte ho.

## Useful commands

```powershell
.\.venv\Scripts\ghost.exe run --repo YOUR_REPO_NAME --once --dry-run
.\.venv\Scripts\ghost.exe review latest
.\.venv\Scripts\ghost.exe approve latest
.\.venv\Scripts\ghost.exe status
.\.venv\Scripts\ghost.exe pause
.\.venv\Scripts\ghost.exe resume
.\.venv\Scripts\ghost.exe daemon
```

`daemon` scheduling process chalata hai; terminal band karne par rukega. OS startup service automatically install nahi hoti. Wizard first test ke liye quiet hours disabled rakhta hai; daily time 10:00, Asia/Kolkata hai. Personal schedule `~/.ghost-contributor/policy.toml` mein set karo.

## Package files

| File/folder | Purpose |
|---|---|
| `setup-windows.bat` | Install + existing-model selector + real repo setup |
| `start-ollama-local.bat` | Existing Ollama ko local-only mode mein start karna |
| `start-ghost.bat` | Subsequent dashboard launch |
| `start-demo.bat` | Fixed fixture demo; AI generation nahi hoti |
| `src/ghost_contributor/` | Complete editable backend |
| `src/ghost_contributor/web/` | Dashboard source |
| `tests/` | Safety/integration tests |
| `docs/ARCHITECTURE.md` | Detailed system design |
| `docs/PRD-COVERAGE.md` | Working versus pending features |
| `TROUBLESHOOTING.md` | Errors aur solutions |

Tumhare actual seven models, hardware aur Windows machine par inference abhi verify nahi hui. Linux par `qwen2.5-coder:7b` ka actual dashboard → approval → Git commit run verify hua hai; `docs/REAL-RUN.md` mein record hai. Automated tests aur contract checks ka result `test-results.txt` mein hai. Setup tumhe real local run test karne deta hai.

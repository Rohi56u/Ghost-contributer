# Setup and first-run troubleshooting

| Message/symptom | What to do |
|---|---|
| Python missing/incompatible | Install Python 3.11–3.13; 3.12 tested. Reopen terminal. |
| Git not found | Install Git for Windows and reopen terminal. |
| Ollama unavailable | Start `start-ollama-local.bat`; check configured loopback host/port. |
| Port 11434 in use | Quit old Ollama tray instance before starting the local-only launcher. |
| Fewer than seven models shown | Compare `ollama list` and `ghost models`; check Windows user, Ollama instance and custom `OLLAMA_MODELS` directory. |
| Cloud/embedding model refused | Choose an installed local coding/instruction text-generation model. |
| Exact model missing | Copy the full name from `ghost models` into `ghost policy REPO --model "NAME"`. |
| Local-only confirmation required | Configure/restart Ollama cloud-disabled first, then complete setup acknowledgement. |
| Model HTTP error / memory issue | Inspect local Ollama logs; choose a smaller installed model or free RAM/VRAM. |
| Timeout | Set `ghost policy REPO --timeout 300` (maximum) or choose a smaller model. |
| Invalid JSON/schema/evidence | No source was changed. Retry manually or select another instruction model; do not treat fixture output as actual model validation. |
| Dirty tree | Inspect `git status`; commit intended changes or safely move your work. Ghost never automatically stashes/deletes it. |
| Unsupported bytes / checkout filter | Git and disk bytes differ, often from autocrlf. Test the isolated sample first; decide your repository line-ending policy deliberately. |
| Quiet hours | Wait for configured window or edit policy. Equal quiet start/end disables quiet hours. Wizard policies permit the first test at any time. |
| No supported gap | Use the wizard sample or explicit backlog. Existing docs, decorated/one-line functions and unsupported languages may be skipped. |
| Pending proposal exists | Review, approve or reject it first. |
| Original file unchanged after approval | Expected: inspect the dedicated `ghost/…` branch with `git show`. |
| Base/policy changed | Reject stale proposal; generate a fresh eligible one. |
| Rejected sample gives no new proposal | Same target/base is deduplicated. Create another isolated sample through setup for model comparisons. |
| Dashboard unauthorized | Use the complete URL including token from the current dashboard process. |
| Port 8765 in use | Close previous dashboard or use `ghost dashboard --port 8766`. |

For commit/push uncertainty, follow `docs/SECURITY.md`. The fixed demo and local HTTP fixtures do not prove every installed model generates correct documentation.

# Open Palm privacy policy

Open Palm is a hackathon app for Even Realities G2 glasses that shows how to sign a sentence in American Sign Language. Developer: Abdullah Rashid (GitHub: tanushsavadi/GhostBuild, branch `test_sim`).

## What the app uses, and why

| Permission | Used for | What happens to the data |
|---|---|---|
| **G2 microphone** (`g2-microphone`) | Only after you choose *Speak a sentence* or *Prepare a conversation* in the menu, until you tap. The phone's *Hold to talk* button does the same. | The recording is sent once to the developer's server, which forwards it to ElevenLabs for speech-to-text and returns the text. **No audio is stored**, by the app or the server. |
| **Network** (`network`) | Talking to the developer's server for speech-to-text, sign order and conversation prep. | See below. |

The app uses no location, camera, photos or contacts, and has no accounts.

## Servers the app talks to

- **The developer's server** (laptop), reached at `https://NGROK_DOMAIN` (an ngrok address run by the developer; the only address in the app's network whitelist). It does three things:
  - **speech** (`/api/stt`): passes your recording to **ElevenLabs** (`api.elevenlabs.io`) and returns the text;
  - **sign order** (`/api/translate`): the sentence text is processed by an AI model running **on the developer's laptop** (Ollama); it is not sent to any third party;
  - **conversation prep** (`/api/prepare`): the situation you describe (text) is sent to a **CREAO** agent (`agent.creao.ai`), which plans likely sentences.
- No analytics or advertising services are used.

## What is stored

- **By default, nothing personal.** The last prepared phrasebook (sentences for a situation you described) is kept on the developer's laptop so it can be shown again.
- **Only if you turn on "Remember my sentences"** on the phone page: the sentences you sign and the signs you open the full description for are kept as text on the developer's laptop, so conversation prep can reuse them. *Forget my history* deletes them.
- Third parties (ElevenLabs, CREAO) handle data under their own policies; the app sends them only what is described above.

## Contact

Open an issue on the GitHub repository above.

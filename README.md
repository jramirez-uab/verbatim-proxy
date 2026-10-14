# verbatim-proxy

**Keep file names verbatim when a coding agent works in a language other than English.**

An OpenAI-compatible proxy (one file, Python standard library only) that sits between your agent client (e.g. [opencode](https://opencode.ai)) and your
model server (e.g. vLLM). In the **user** messages it wraps file names and paths in backticks, so the model treats them as literals.

## The problem

Running a local model as a Linux sysadmin agent **in Spanish**, we saw the model pick a different file name from the one we asked for (the client
only executes the tool call; the name is the model's choice):

| Asked for | Written |
|---|---|
| `procesos.csv` | `processes.csv` |
| `usuarios.txt` | `users.txt` |

It is **not translation**. When we replaced the output names with Spanish words unrelated to the system (`tortuga.txt`, `zapatilla.csv`, `castana.txt`),
the model kept **34 of 34**. It changes only words it recognizes as a system concept (processes, users, errors) and "normalizes" them to the English name
such a file usually has, the same way "the password file" becomes `/etc/passwd`. With the same tasks written in English the problem does not appear.

## Results

Two 9B models (NeoHorse-1-9B and Ornith-1.5-9B, EXL3 quantizations, vLLM), 20 sysadmin agent tasks run with `opencode run` in a sandbox with
deterministic checks (10 regular + 10 control tasks), several runs:

| Variant | Tasks | File name changed | Agent success |
|---|---|---|---|
| nothing | 340 | 18 (5.3 %) | 75-82 % |
| instruction in `AGENTS.md` ("use the exact file names, do not translate them") | 120 | 5 (4.2 %) | ≈ same |
| **verbatim-proxy** | **360** | **0** | **88-92 %** (+6 to +10 points, also on the control tasks) |
| same tasks in English, no proxy | 40 | 0 | 85 % |

Instructions in the agent prompt barely help; marking the literals does. The same pattern shows up with larger models (Qwen3.8-27B family).

## Usage

```bash
python3 verbatim_proxy.py --upstream http://127.0.0.1:8000 --port 8199   # your vLLM (or any OpenAI-compatible server) on 8000
python3 verbatim_proxy.py --test                                          # show what it marks
```

Then point the client at the proxy instead of the server. In opencode, for example:

```json
"options": { "baseURL": "http://127.0.0.1:8199/v1" }
```

What `--test` prints:

```
Analiza app.log y escribe errores.txt con los 3 errores.
  -> Analiza `app.log` y escribe `errores.txt` con los 3 errores.
Corrige mi-app.service aquí; mira /opt/miapp/bin y passwd.txt.
  -> Corrige `mi-app.service` aquí; mira `/opt/miapp/bin` y `passwd.txt`.
Versión 2.5 y 3.14 no son ficheros; tampoco e.g. o 10.0.4.17
  -> Versión 2.5 y 3.14 no son ficheros; tampoco e.g. o 10.0.4.17
```

## What it does and does not touch

- Marks, in **user** messages of `/v1/chat/completions`: names with a common extension (`txt csv md sh yaml yml json conf cfg ini log service timer
  socket nft py sql toml xml html js ts env pem key crt`, optionally with a directory) and absolute paths with at least two components (`/opt/app/bin`).
- Leaves alone: text already in backticks or code blocks, version numbers and IP addresses, the system prompt, tool results, the model's answers.
- Forwards everything else unchanged (other endpoints, headers, streaming). If a request body is not JSON it understands, it forwards it as it came.
- It does not add authentication: listen on `127.0.0.1` (the default) or put it behind whatever already protects your server.

## Limitations

- Only the extensions above are recognized; a name without one (`Makefile`, `procesos`) is not marked. Edit `EXT` in the script to add yours.
- Measured in Spanish with Qwen-based models; we expect the same in other languages, but we have not measured it.
- It fixes literal names, not missing knowledge: wrong command options (Slurm, systemd timers) are a different problem.

## License

MIT (see `LICENSE`).

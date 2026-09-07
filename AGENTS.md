# System Changes / Agent Permissions

IMPORTANT: the files you edit should only be in this local repo, NEVER anywhere else on
the system.

You, the agent, should NEVER run commands on the system that would make permanent changes
outside the project's repo directory (except for temporary files).

If a command/process you want to run would affect non-temporary files outside the project
directory, the command/process MUST BE READ-ONLY.

If you are ever confused about what you have permission to do, stop and ask.


## Exception: temporary files / directories

Exceptions to the permission policies:

- Ok: changes to files inside known system temporary directories like `/tmp`.
- Ok: create/update runtime artifacts like `.pyc`
- Ok: to make changes with uv that impact this project's venv ONLY
- OK: changes to the databases defined in this app's docker compose


## Conditional Instructions Index

1. At the start of every session, before responding to the first user prompt or doing any
   task-related work, you MUST ALWAYS look for the index file at
   `~/projects/agent-configs/conditional-instructions-local.yaml` and load it if present.
2. If the local index file is not present, load the remote
   [index file](https://raw.githubusercontent.com/rsyring/agent-configs/refs/heads/main/conditional-instructions.yaml).
3. You MUST NOT load any linked documents from the index UNLESS that document's `when`
   condition applies to the current task.
4. If neither index file can be loaded, stop and report that failure before answering the
   user substantively.
5. WHEN you load a document from the index, notify the user.


# System Commands

- Use ripgrep `/usr/bin/rg` instead of `grep` because it's faster


# File paths prefer dashes

UNLESS it's a `*.py` file, prefer dashes (`-`) in file paths and names instead of
underscores.


# Hypergen Reference

- Find the original Django Hypergen reference files at: `~/projects/django-hypergen`
- Use that repo as a read-only reference when porting or verifying Hypergen behavior.
- In this repo, the runnable example app lives in `./examples`.

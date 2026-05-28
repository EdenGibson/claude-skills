---
name: obsidian
description: "Obsidian CLI reference — run commands against Eden's Obsidian vaults"
user_invocable: true
---

# /obsidian — CLI Reference

Quick reference for Obsidian CLI commands. Use this when working with Eden's Obsidian vaults.

## Executable

```bash
"$HOME/AppData/Local/Programs/Obsidian/Obsidian.com" <command> [options] vault=plog
```

**Must use `Obsidian.com`** (console executable). `Obsidian.exe` / bare `obsidian` silently fails on subcommands (exit 127).

## Vaults

| Vault | Path | Notes |
|---|---|---|
| **plog** | `~/Documents/Obsidian/plog` | Personal notes — **DEFAULT, always use unless told otherwise** |
| **evals** | `~/Documents/Code/Derive/evals` | Derive project evals |

Always append `vault=plog` unless Eden specifies a different vault.

## Key Syntax Rules

- File resolves by name (like wikilinks); path is exact (`folder/note.md`)
- Most commands default to the active file when `file=`/`path=` is omitted
- Quote values with spaces: `name="My Note"`
- Use `\n` for newlines in content

## Commands

### Reading & Searching

| Command | Description | Key Options |
|---|---|---|
| `read file="Name"` | Read file contents | `path=` |
| `search query="text"` | Search vault | `path=`, `limit=`, `case`, `total`, `format=text\|json` |
| `search:context query="text"` | Search with surrounding lines | Same as search |

### Creating & Editing

| Command | Description | Key Options |
|---|---|---|
| `create name="Name"` | Create new file | `content=`, `template=`, `overwrite`, `open` |
| `append file="Name" content="text"` | Append to file | `inline` (no newline) |
| `prepend file="Name" content="text"` | Prepend to file | `inline` |
| `delete file="Name"` | Delete file | `permanent` |
| `move file="Name" to="folder/"` | Move/rename file | |
| `rename file="Name" name="New"` | Rename file | |
| `open file="Name"` | Open in Obsidian | `newtab` |

### Daily Notes

| Command | Description | Key Options |
|---|---|---|
| `daily` | Open daily note | |
| `daily:read` | Read today's daily note | |
| `daily:append content="text"` | Append to daily note | `open` |
| `daily:prepend content="text"` | Prepend to daily note | |

### File System

| Command | Description | Key Options |
|---|---|---|
| `files` | List all files | `folder=`, `ext=`, `total` |
| `folders` | List folders | `folder=`, `total` |

### Tasks

| Command | Description | Key Options |
|---|---|---|
| `tasks` | List tasks | `done`, `todo`, `file=`, `verbose`, `daily`, `status="char"` |
| `task ref="path:line" toggle` | Toggle task | `done`, `todo` |

### Metadata & Links

| Command | Description | Key Options |
|---|---|---|
| `tags` | List tags | `file=`, `counts`, `sort=count` |
| `tag name="tagname"` | Tag info | `total`, `verbose` |
| `properties file="Name"` | List properties | `name=`, `format=yaml\|json` |
| `property:set name= value= file=` | Set frontmatter property | `type=` |
| `property:read name= file=` | Read property value | |
| `links file="Name"` | Outgoing links | `total` |
| `backlinks file="Name"` | Incoming links | `counts`, `total` |
| `orphans` | No incoming links | `total` |
| `deadends` | No outgoing links | `total` |
| `unresolved` | Broken links | `counts`, `verbose` |

### Structure & Info

| Command | Description | Key Options |
|---|---|---|
| `outline file="Name"` | Show headings | `format=tree\|md\|json` |
| `templates` | List templates | |
| `plugins` | List plugins | `filter=core\|community`, `versions` |
| `bookmarks` | List bookmarks | |
| `bookmark file="path"` | Add bookmark | `title=`, `search=`, `url=` |
| `recents` | Recently opened files | |
| `random` | Open random note | `folder=` |
| `vault` | Vault info | `info=name\|path\|files\|size` |
| `wordcount file="Name"` | Word/char count | `words`, `characters` |

## Output Formats

Most list commands support `format=json|tsv|csv` and `total` for counts.

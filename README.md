# Auto Skill Installer / AI 技能自动安装器

`auto-skill-installer` is an open-source skill discovery and installation helper for AI agents. It helps an agent notice when it needs another capability, search local folders plus GitHub-based registries, and install the best matching skill into the target agent's skills directory.

`auto-skill-installer` 是一个面向 AI 智能体的开源技能发现与安装助手。它可以让智能体在工作中发现自己缺少某项能力时，自动搜索本地 skills 和 GitHub 技能仓库，并把最匹配的 skill 安装到目标智能体的技能目录中。

The current implementation is compatible with Codex by default and installs into `$CODEX_HOME/skills`, while the registry model and CLI are designed to be reused by other agent runtimes.

当前实现默认兼容 Codex，并安装到 `$CODEX_HOME/skills`；同时，技能仓库格式和命令行工具也面向其他智能体运行环境设计。

## What It Does / 功能

- Searches already installed skills before going to the network
- Reads configured GitHub skill registries and ranks likely matches
- Installs a remote skill only when the selected directory contains `SKILL.md`
- Lets you add your own organization or personal skill registry
- Uses Codex as the default install target, but keeps the registry and CLI agent-friendly

- 先搜索已经安装的本地 skills，再访问远程仓库
- 读取已配置的 GitHub skill registries，并按匹配度排序
- 只安装包含 `SKILL.md` 的有效 skill 目录
- 支持添加团队、组织或个人维护的技能仓库
- 默认安装目标是 Codex，但仓库格式和 CLI 可扩展到其他智能体

## Layout / 项目结构

- `skills/auto-skill-installer/`: installable skill / 可安装的 skill
- `skills/auto-skill-installer/scripts/auto_install.py`: CLI entry point / 命令行入口
- `skills/auto-skill-installer/assets/registry-sources.json`: bundled default registries / 默认远程源配置

## Quick Start / 快速开始

```powershell
python skills/auto-skill-installer/scripts/auto_install.py search --need "figma design generation"
python skills/auto-skill-installer/scripts/auto_install.py ensure --need "github pull request review comments" --force
python skills/auto-skill-installer/scripts/auto_install.py add-source --name my-team --repo your-org/agent-skills --path skills
```

## Manual Install for Codex / Codex 手动安装

For Codex, copy `skills/auto-skill-installer` into your local Codex skills directory.

如果用于 Codex，把 `skills/auto-skill-installer` 安装到你的本地 Codex skills 目录：

```powershell
$dest = Join-Path $HOME ".codex\\skills\\auto-skill-installer"
Copy-Item -Recurse -LiteralPath ".\\skills\\auto-skill-installer" -Destination $dest
```

Restart Codex after installing new skills so they are auto-discovered.

安装新 skill 后，请重启 Codex，让它自动发现新技能。

Other AI agents can reuse the same registry format and CLI by pointing the install destination at their own skills directory with `--dest`.

其他 AI 智能体可以复用同样的 registry 格式和 CLI，并通过 `--dest` 指向自己的技能目录。

可以的话可以赞赏一下吗喵

<img width="1170" height="1061" alt="download" src="https://github.com/user-attachments/assets/fbf1b1e0-fb7b-4410-9f80-5122437a8488" />





"""
CLI Shell 补全脚本生成器
"""

from typing import Literal


def completion_script(shell: Literal["bash", "zsh", "fish"]) -> str:
    """生成 shell 补全脚本

    Args:
        shell: shell 类型（bash/zsh/fish）

    Returns:
        补全脚本内容
    """
    if shell == "bash":
        return """# kb bash 补全脚本
_kb_completion() {
    local cur prev words cword
    _init_completion || return

    # 一级命令
    local commands="init doctor ingest compile query status promote quality vault config version"

    # vault 子命令
    local vault_commands="seed push status"

    # promote --to 选项
    local promote_targets="wiki curated obsidian"

    # query --mode 选项
    local query_modes="concept summary vector combined all"

    case "${prev}" in
        kb)
            COMPREPLY=($(compgen -W "${commands}" -- "${cur}"))
            ;;
        vault)
            COMPREPLY=($(compgen -W "${vault_commands}" -- "${cur}"))
            ;;
        promote)
            COMPREPLY=($(compgen -W "SRC-" -- "${cur}"))
            _kb_complete_src_ids
            ;;
        --to)
            if __kb_is_promote_command; then
                COMPREPLY=($(compgen -W "${promote_targets}" -- "${cur}"))
            fi
            ;;
        --mode)
            COMPREPLY=($(compgen -W "${query_modes}" -- "${cur}"))
            ;;
        *)
            case "${words[1]}" in
                promote)
                    if [[ "${cur}" == --* ]]; then
                        COMPREPLY=($(compgen -W "--to" -- "${cur}"))
                    fi
                    ;;
                compile)
                    COMPREPLY=($(compgen -W "--limit --concurrency --openrouter --dry-run" -- "${cur}"))
                    ;;
                query)
                    COMPREPLY=($(compgen -W "--mode --top-k" -- "${cur}"))
                    ;;
                quality)
                    COMPREPLY=($(compgen -W "--report --fix" -- "${cur}"))
                    ;;
                vault)
                    case "${words[2]}" in
                        seed)
                            COMPREPLY=($(compgen -W "--limit" -- "${cur}"))
                            ;;
                    esac
                    ;;
                ingest)
                    COMPREPLY=($(compgen -W "--dry-run" -- "${cur}"))
                    COMPREPLY+=($(compgen -f -- "${cur}"))
                    ;;
            esac
            ;;
    esac
}

_kb_is_promote_command() {
    local i
    for ((i=1; i<COMP_CWORD; i++)); do
        if [[ "${COMP_WORDS[i]}" == "promote" ]]; then
            return 0
        fi
    done
    return 1
}

_kb_complete_src_ids() {
    local workspace="${WORKSPACE:-${HOME}/.knowledge-base}"
    local manifest_dir="${workspace}/manifests/sources"
    if [[ -d "${manifest_dir}" ]]; then
        local ids=($(compgen -W "$(ls ${manifest_dir} 2>/dev/null | grep -o 'SRC-[0-9]*')" -- "${cur}"))
        COMPREPLY+=("${ids[@]}")
    fi
}

complete -F _kb_completion kb
"""
    elif shell == "zsh":
        return """# kb zsh 补全脚本
#compdef kb

_kb() {
    local -a commands subcommands vault_commands promote_targets query_modes

    commands=(
        'init:初始化工作区'
        'doctor:环境诊断'
        'ingest:Phase 1 摄入文件'
        'compile:Phase 2 编译文档'
        'query:Phase 3 查询知识库'
        'status:显示系统状态'
        'promote:Promote 操作'
        'quality:质量管理'
        'vault:Obsidian 联动'
        'config:显示配置'
        'version:显示版本'
    )

    vault_commands=(
        'seed:从 Obsidian 拉取笔记'
        'push:推送知识到 Obsidian'
        'status:显示同步状态'
    )

    promote_targets=(wiki curated obsidian)
    query_modes=(concept summary vector combined all)

    case $state in
        command)
            _describe 'command' commands
            ;;
        vault_command)
            _describe 'vault command' vault_commands
            ;;
        promote_target)
            _describe 'target' promote_targets
            ;;
        query_mode)
            _describe 'mode' query_modes
            ;;
    esac
}

_kb "$@"
"""
    else:  # fish
        return """# kb fish 补全脚本
complete -c kb -f

complete -c kb -n __fish_use_subcommand -a init -d "初始化工作区"
complete -c kb -n __fish_use_subcommand -a doctor -d "环境诊断"
complete -c kb -n __fish_use_subcommand -a ingest -d "Phase 1: 摄入文件"
complete -c kb -n __fish_use_subcommand -a compile -d "Phase 2: 编译文档"
complete -c kb -n __fish_use_subcommand -a query -d "Phase 3: 查询知识库"
complete -c kb -n __fish_use_subcommand -a status -d "显示系统状态"
complete -c kb -n __fish_use_subcommand -a promote -d "Promote 操作"
complete -c kb -n __fish_use_subcommand -a quality -d "质量管理"
complete -c kb -n __fish_use_subcommand -a config -d "显示配置"
complete -c kb -n __fish_use_subcommand -a version -d "显示版本"

# vault 子命令
complete -c kb -n "__fish_seen_subcommand_from vault" -a seed -d "从 Obsidian 拉取笔记"
complete -c kb -n "__fish_seen_subcommand_from vault" -a push -d "推送知识到 Obsidian"
complete -c kb -n "__fish_seen_subcommand_from vault" -a status -d "显示同步状态"

# promote 选项
complete -c kb -n "__fish_seen_subcommand_from promote" -l to -k -a "wiki curated obsidian"

# query 选项
complete -c kb -n "__fish_seen_subcommand_from query" -l mode -k -a "concept summary vector combined all"
complete -c kb -n "__fish_seen_subcommand_from query" -l top-k

# compile 选项
complete -c kb -n "__fish_seen_subcommand_from compile" -l limit
complete -c kb -n "__fish_seen_subcommand_from compile" -l concurrency
complete -c kb -n "__fish_seen_subcommand_from compile" -l openrouter
complete -c kb -n "__fish_seen_subcommand_from compile" -l dry-run

# quality 选项
complete -c kb -n "__fish_seen_subcommand_from quality" -l report
complete -c kb -n "__fish_seen_subcommand_from quality" -l fix

# ingest 选项
complete -c kb -n "__fish_seen_subcommand_from ingest" -l dry-run
"""

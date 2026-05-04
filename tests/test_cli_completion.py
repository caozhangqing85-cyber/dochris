"""测试 CLI 补全生成"""

from dochris.cli.cli_completion import completion_script


class TestCLICompletion:
    def test_bash_completion_output(self) -> None:
        """bash 补全输出格式"""
        script = completion_script("bash")
        assert script is not None
        assert len(script) > 0
        # 验证包含关键子命令
        assert "init" in script
        assert "compile" in script
        assert "query" in script
        assert "promote" in script
        # 验证 bash 函数定义
        assert "_kb_completion()" in script
        assert "complete -F _kb_completion kb" in script

    def test_zsh_completion_output(self) -> None:
        """zsh 补全输出格式"""
        script = completion_script("zsh")
        assert script is not None
        assert len(script) > 0
        # 验证包含关键子命令
        assert "init" in script
        assert "compile" in script
        assert "query" in script
        # 验证 zsh 补全标记
        assert "#compdef kb" in script or "_describe 'command'" in script

    def test_fish_completion_output(self) -> None:
        """fish 补全输出格式"""
        script = completion_script("fish")
        assert script is not None
        assert len(script) > 0
        # 验证包含关键子命令
        assert "init" in script
        assert "compile" in script
        # 验证 fish 补全语法
        assert "complete -c kb" in script

    def test_completion_includes_subcommands(self) -> None:
        """补全包含常见子命令"""
        script = completion_script("bash")
        common_commands = ["init", "doctor", "ingest", "compile", "query", "status", "promote"]
        for cmd in common_commands:
            assert cmd in script, f"缺少子命令: {cmd}"

    def test_completion_includes_options(self) -> None:
        """补全包含常见选项"""
        script = completion_script("bash")
        # 验证一些常见选项
        assert "--to" in script or "--mode" in script or "--limit" in script

"""测试消息截取功能。"""
import pytest

from app.api.messages import _truncate_user_input, _apply_truncation_strategy


class TestTruncateUserInput:
    """测试用户输入截取函数。"""

    def test_no_truncation_needed(self):
        """测试不需要截取的情况。"""
        content = "a" * 500
        result = _truncate_user_input(content, 1000, "...")
        assert result == content
        assert len(result) == 500

    def test_truncation_with_warning(self):
        """测试需要截取并添加警告的情况。"""
        content = "a" * 1500
        result = _truncate_user_input(content, 1000, "...(消息已截取)")
        assert len(result) == 1000 + len("...(消息已截取)")
        assert result.endswith("...(消息已截取)")

    def test_truncation_without_warning(self):
        """测试需要截取但不添加警告的情况。"""
        content = "a" * 1500
        result = _truncate_user_input(content, 1000, "")
        assert len(result) == 1000
        assert result == "a" * 1000

    def test_exact_length(self):
        """测试恰好等于最大长度的情况。"""
        content = "a" * 1000
        result = _truncate_user_input(content, 1000, "...")
        assert result == content
        assert len(result) == 1000


class TestApplyTruncationStrategy:
    """测试历史消息截取策略函数。"""

    def test_empty_messages(self):
        """测试空消息列表。"""
        result = _apply_truncation_strategy([], max_history=20)
        assert result == []

    def test_only_system_messages(self):
        """测试只有 system 消息的情况。"""
        messages = [
            {"role": "system", "content": "system prompt"},
            {"role": "system", "content": "file notification"},
        ]
        result = _apply_truncation_strategy(messages, max_history=20)
        assert len(result) == 2
        assert result[0]["content"] == "system prompt"
        assert result[1]["content"] == "file notification"

    def test_first_user_message_kept(self):
        """测试第一条用户消息被保留。"""
        messages = [
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "first user message"},
            {"role": "user", "content": "second user message"},
        ]
        result = _apply_truncation_strategy(messages, max_history=20)
        # 应该保留 system 和第一条 user 消息
        assert len(result) == 2
        assert result[0]["role"] == "system"
        assert result[1]["role"] == "user"
        assert result[1]["content"] == "first user message"

    def test_recent_assistants_kept(self):
        """测试最近 N 条 assistant 消息被保留。"""
        messages = [
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "user1"},
            {"role": "assistant", "content": "assist1", "tool_calls": [{"id": "call_1"}]},
            {"role": "user", "content": "user2"},
            {"role": "assistant", "content": "assist2", "tool_calls": [{"id": "call_2"}]},
        ]
        result = _apply_truncation_strategy(messages, max_history=1)
        # max_history=1，只保留最新的 1 条 assistant
        # 同时也会保留第一条用户消息和 system 消息
        assert len(result) == 3
        assert result[0]["role"] == "system"
        assert result[1]["role"] == "user"
        assert result[1]["content"] == "user1"
        assert result[2]["role"] == "assistant"
        assert result[2]["content"] == "assist2"

    def test_tool_messages_with_assistant(self):
        """测试 tool 消息与其关联的 assistant 一起保留。"""
        messages = [
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "user1"},
            {
                "role": "assistant",
                "content": "assist1",
                "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "read", "arguments": "{}"}}],
            },
            {"role": "tool", "tool_call_id": "call_1", "content": "tool result"},
        ]
        result = _apply_truncation_strategy(messages, max_history=20)
        # 应该保留 system、第一条 user、assistant 和关联的 tool
        assert len(result) == 4
        assert result[0]["role"] == "system"
        assert result[1]["role"] == "user"
        assert result[2]["role"] == "assistant"
        assert result[3]["role"] == "tool"
        assert result[3]["tool_call_id"] == "call_1"

    def test_complex_scenario(self):
        """测试复杂场景：多条消息混合。"""
        messages = [
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "user1"},
            {"role": "assistant", "content": "assist1", "tool_calls": [{"id": "call_1"}]},
            {"role": "tool", "tool_call_id": "call_1", "content": "result1"},
            {"role": "system", "content": "file created notification"},
            {"role": "user", "content": "user2"},
            {"role": "assistant", "content": "assist2", "tool_calls": [{"id": "call_2"}]},
            {"role": "tool", "tool_call_id": "call_2", "content": "result2"},
            {"role": "user", "content": "user3"},
            {"role": "assistant", "content": "assist3", "tool_calls": [{"id": "call_3"}]},
            {"role": "tool", "tool_call_id": "call_3", "content": "result3"},
        ]
        result = _apply_truncation_strategy(messages, max_history=2)
        # max_history=2，保留最新的 2 条 assistant
        # 预期：system, user1, system(通知), assist2, tool2, assist3, tool3
        assert len(result) == 7
        assert result[0]["role"] == "system"
        assert result[0]["content"] == "system prompt"
        assert result[1]["role"] == "user"
        assert result[1]["content"] == "user1"
        assert result[2]["role"] == "system"
        assert result[2]["content"] == "file created notification"
        # assist1 应该被截取掉（不在最新 2 条中）
        assert result[3]["role"] == "assistant"
        assert result[3]["content"] == "assist2"
        assert result[4]["role"] == "tool"
        assert result[5]["role"] == "assistant"
        assert result[5]["content"] == "assist3"
        assert result[6]["role"] == "tool"

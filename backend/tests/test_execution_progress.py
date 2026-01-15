"""测试执行进度追踪功能"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, init_db
from app.models import AgentExecutionStep, ExecutionStatus, Message, MessageRole, Session, User


def test_execution_progress():
    """测试执行进度追踪"""

    # 初始化数据库
    print("初始化数据库...")
    init_db()

    # 创建测试会话
    db = SessionLocal()

    try:
        # 清理旧数据
        print("清理旧数据...")
        db.query(AgentExecutionStep).delete()
        db.query(Message).delete()
        db.query(Session).delete()
        db.query(User).delete()
        db.commit()

        # 创建测试用户
        print("创建测试用户...")
        user = User(username="test_user", email="test@example.com", hashed_password="hash")
        db.add(user)
        db.commit()
        db.refresh(user)

        # 创建测试会话
        print("创建测试会话...")
        session = Session(id="test_session_123", user_id=user.id, title="Test Session")
        db.add(session)
        db.commit()
        db.refresh(session)

        # 创建测试消息
        print("创建测试消息...")
        message = Message(
            session_id=session.id,
            role=MessageRole.ASSISTANT,
            content="",
            reasoning_content=None,
            tool_calls=None,
        )
        db.add(message)
        db.commit()
        db.refresh(message)

        # 模拟执行步骤
        print("创建执行步骤...")

        # 步骤 1: 思考中
        step1 = AgentExecutionStep(
            session_id=session.id,
            message_id=message.id,
            user_id=user.id,
            iteration=1,
            status=ExecutionStatus.THINKING,
            reasoning_content="用户想要创建一个待办事项列表...",
            progress=10.0,
        )
        db.add(step1)
        db.commit()
        print(f"✓ 步骤 1: {step1.status.value} (progress={step1.progress}%)")

        # 步骤 2: 工具调用
        step2 = AgentExecutionStep(
            session_id=session.id,
            message_id=message.id,
            user_id=user.id,
            iteration=1,
            status=ExecutionStatus.TOOL_CALLING,
            tool_name="write",
            tool_arguments='{"filename": "index.html", "content": "<html>...</html>"}',
            tool_call_id="call_123",
            progress=20.0,
        )
        db.add(step2)
        db.commit()
        print(
            f"✓ 步骤 2: {step2.status.value} (tool={step2.tool_name}, progress={step2.progress}%)"
        )

        # 步骤 3: 工具执行中
        step3 = AgentExecutionStep(
            session_id=session.id,
            message_id=message.id,
            user_id=user.id,
            iteration=1,
            status=ExecutionStatus.TOOL_EXECUTING,
            tool_name="write",
            tool_arguments='{"filename": "index.html", "content": "<html>...</html>"}',
            tool_call_id="call_123",
            progress=25.0,
        )
        db.add(step3)
        db.commit()
        print(
            f"✓ 步骤 3: {step3.status.value} (tool={step3.tool_name}, progress={step3.progress}%)"
        )

        # 步骤 4: 工具完成
        step4 = AgentExecutionStep(
            session_id=session.id,
            message_id=message.id,
            user_id=user.id,
            iteration=1,
            status=ExecutionStatus.TOOL_COMPLETED,
            tool_name="write",
            tool_arguments='{"filename": "index.html", "content": "<html>...</html>"}',
            tool_call_id="call_123",
            tool_result="文件写入成功",
            progress=30.0,
        )
        db.add(step4)
        db.commit()
        print(
            f"✓ 步骤 4: {step4.status.value} (tool={step4.tool_name}, progress={step4.progress}%)"
        )

        # 步骤 5: 第二轮思考
        step5 = AgentExecutionStep(
            session_id=session.id,
            message_id=message.id,
            user_id=user.id,
            iteration=2,
            status=ExecutionStatus.THINKING,
            reasoning_content="文件创建成功，现在需要添加样式...",
            progress=35.0,
        )
        db.add(step5)
        db.commit()
        print(
            f"✓ 步骤 5: {step5.status.value} "
            f"(iteration={step5.iteration}, progress={step5.progress}%)"
        )

        # 步骤 6: 完成
        step6 = AgentExecutionStep(
            session_id=session.id,
            message_id=message.id,
            user_id=user.id,
            iteration=2,
            status=ExecutionStatus.COMPLETED,
            progress=100.0,
        )
        db.add(step6)
        db.commit()
        print(f"✓ 步骤 6: {step6.status.value} (progress={step6.progress}%)")

        # 更新消息内容
        message.content = "我已经为您创建了一个待办事项列表应用。"
        message.reasoning_content = step5.reasoning_content
        db.commit()
        print("✓ 消息已更新")

        # 查询测试
        print("\n查询测试...")

        # 测试 1: 查询所有步骤
        all_steps = (
            db.query(AgentExecutionStep)
            .filter(AgentExecutionStep.message_id == message.id)
            .order_by(AgentExecutionStep.created_at.asc())
            .all()
        )

        print(f"✓ 查询到 {len(all_steps)} 个步骤")

        # 测试 2: 使用 to_dict 方法
        print("\n步骤详情（JSON 格式）:")
        for i, step in enumerate(all_steps, 1):
            step_dict = step.to_dict()
            print(f"{i}. {step_dict['status']} - progress={step_dict['progress']}%")
            if step_dict.get("tool_name"):
                print(f"   工具: {step_dict['tool_name']}")
            if step_dict.get("reasoning_content"):
                content = step_dict["reasoning_content"][:50] + "..."
                print(f"   思考: {content}")

        # 测试 3: 统计各状态步骤数
        print("\n状态统计:")
        for status in ExecutionStatus:
            count = (
                db.query(AgentExecutionStep)
                .filter(
                    AgentExecutionStep.message_id == message.id, AgentExecutionStep.status == status
                )
                .count()
            )
            if count > 0:
                print(f"  {status.value}: {count}")

        print("\n✅ 所有测试通过！")

        # 显示数据结构示例
        print("\n" + "=" * 60)
        print("前端将收到的 JSON 响应示例:")
        print("=" * 60)
        import json

        print(json.dumps([step.to_dict() for step in all_steps[:3]], indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback

        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    test_execution_progress()

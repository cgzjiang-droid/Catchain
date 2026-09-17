import pytest


def test_agent_uses_observations_to_choose_the_next_action() -> None:
    try:
        from catchain.learning_labs.agent_loop import Finish, ToolCall, run_agent
    except ModuleNotFoundError:
        pytest.fail("the educational agent loop has not been implemented")

    def decide(goal: str, observations: tuple[str, ...]) -> ToolCall | Finish:
        if not observations:
            return ToolCall(name="parse_pdf", argument="project.pdf")
        if observations[-1] == "":
            return ToolCall(name="ocr_pdf", argument="project.pdf")
        return Finish(answer=f"已取得文本：{observations[-1]}")

    tools = {
        "parse_pdf": lambda _: "",
        "ocr_pdf": lambda _: "ACM0002 project text",
    }

    result = run_agent(
        goal="取得可用于抽取的项目文档文本",
        decide=decide,
        tools=tools,
        max_steps=3,
    )

    assert result.answer == "已取得文本：ACM0002 project text"
    assert result.observations == ("", "ACM0002 project text")
    assert result.steps == 3

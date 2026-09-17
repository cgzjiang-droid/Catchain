"""A minimal Agent Loop for the Hello-Agents chapter 1 learning lab."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class ToolCall:
    """A decision to execute one named tool."""

    name: str
    argument: str


@dataclass(frozen=True)
class Finish:
    """A decision to stop the loop with a final answer."""

    answer: str


@dataclass(frozen=True)
class AgentResult:
    """The final answer and observable execution history."""

    answer: str
    observations: tuple[str, ...]
    steps: int


DecisionMaker = Callable[[str, tuple[str, ...]], ToolCall | Finish]
Tool = Callable[[str], str]


def run_agent(
    *,
    goal: str,
    decide: DecisionMaker,
    tools: Mapping[str, Tool],
    max_steps: int,
) -> AgentResult:
    """Run decisions and tools until the decision maker chooses to finish."""

    observations: list[str] = []

    for step in range(1, max_steps + 1):
        decision = decide(goal, tuple(observations))
        if isinstance(decision, Finish):
            return AgentResult(
                answer=decision.answer,
                observations=tuple(observations),
                steps=step,
            )

        observation = tools[decision.name](decision.argument)
        observations.append(observation)

    raise RuntimeError("agent reached max_steps without finishing")

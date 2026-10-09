from lightdash_companion_integration_spike.lightdash import analyst_prompt

SERVER_PROMPT = """## Query Building Workflow

0. `get_context`: select scope.
1. `grep_fields`: discover fields.
2. `get_metadata`: confirm metadata before querying.
5. `get_query_result`: poll running queries.
6. `render_chart`: render completed metric queries.

## Rules

- Prefer `run_metric_query`; use `run_sql` only for ad-hoc queries.
- If still ambiguous, ask the user which to use; never guess"""


class TestAdapt:
    def test_removes_lines_that_name_tools_the_agent_lacks(self) -> None:
        adapted = analyst_prompt.adapt(prompt=SERVER_PROMPT)

        assert "render_chart" not in adapted
        assert "get_context" not in adapted
        assert "run_sql" not in adapted

    def test_keeps_the_guidance_the_agent_can_act_on(self) -> None:
        adapted = analyst_prompt.adapt(prompt=SERVER_PROMPT)

        assert "`get_metadata`: confirm metadata before querying" in adapted
        assert "never guess" in adapted


# Exercise 2: Build tools for your agent

**Time:** 20 minutes

## The brief

Give your agent tools that answer questions about this week's 311 data, starting with the room challenge.

Your coding agent writes the code.
Your job is the design: which tools exist, what each one returns, and how the docstrings steer the model.
An MCP server is an interface for a model, so a tool for every column, or one that returns whole tables, fails this brief even if it works.

## Required tools

The tests call these names and arguments.
How they work inside, the docstrings, and any extra tools are up to you.

| Tool | Arguments | Returns |
| --- | --- | --- |
| `search_requests` | `service`, `neighborhood`, `status` (`Open` or `Closed`), `limit` (1 to 50, default 20). All optional. | Matching requests, newest first, as dicts with the fields of `sf311.data.Request`. |
| `count_requests` | `service`, `neighborhood`, `group_by`. All optional. `group_by` is one of `neighborhood`, `service`, `agency`, `source`, `weekday`, `status`. | A number. With `group_by`: a dict of group to count, largest first, at most 50 groups. |
| `median_close_hours` | `service`, `group_by` (`neighborhood` or `agency`). Both optional. | Median hours from opened to closed, rounded to 0.1. With `group_by`: a dict, fastest first, leaving out groups with fewer than 10 closed requests. |
| `get_request` | `request_id` | One request. |

All four are read-only.
Names must match `dataset_info` exactly.
An unknown service or neighborhood raises a `ToolError` that suggests the closest real names.

## Steps

1. Ask your coding agent:

   ```text
   Read AGENTS.md and exercises/02-build-tools.md, then build the four tools in server.py. Run tests/test_ex2.py until it passes.
   ```

2. Read the docstrings it wrote.
   The model reads them on every turn, so check that each one says when to use that tool and when to use another.

3. When `uv run pytest tests/test_ex2.py` passes, commit and push.
   The push starts a new build. Wait for `Live` on the **Deployments** page.

## Prove it

1. In Claude Code, type `/mcp` and reconnect `sf-311`, so the client loads your new tools.
2. Type `/clear` to start a fresh conversation, then ask:

   ```text
   Solve my Exercise 2 room challenge using only the sf-311 and room MCP tools. My handle is <your-handle>.
   ```

3. When the answer is right, the room server asks whether to post your handle to the room screen.
   Say yes. Your handle appears on the projector.
4. Open **Logs** for your server and find the calls the agent made to answer. That row is the only record of what your agent did with your data, and it is where you look when an answer is wrong.

Claude Desktop cannot show the confirmation form.
There, tell the agent to pass `post_to_screen=true` to `submit_answer`.

## Stretch goals

- Add a resource that describes the dataset's columns, and check whether the model reads it.
- Open a pull request instead of pushing to main. FastMCP Gateway builds it at its own preview URL, so you can test a change before it reaches your main URL.

## If you fall behind

```bash
cp solutions/ex2/server.py server.py
git commit -am "Use the Exercise 2 solution" && git push
```

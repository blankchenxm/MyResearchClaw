import ast
import json
import os
import tempfile
import unittest

import serve


class CodexServerTests(unittest.TestCase):
    def test_serve_module_parses(self):
        with open(serve.__file__, encoding="utf-8") as source:
            ast.parse(source.read())

    def test_default_command_uses_codex_search_and_default_model(self):
        old_model = serve.MODEL
        try:
            serve.MODEL = ""
            command = serve.build_codex_command("do the task")
        finally:
            serve.MODEL = old_model

        self.assertEqual(command[0], serve.RESOLVED_CODEX_BIN)
        self.assertIn("--search", command)
        self.assertIn("exec", command)
        self.assertIn("--json", command)
        self.assertIn("sandbox_workspace_write.network_access=true", command)
        self.assertNotIn("--model", command)
        self.assertEqual(command[-1], "do the task")

    def test_model_override_is_forwarded(self):
        command = serve.build_codex_command("do the task", "custom-model")
        index = command.index("--model")
        self.assertEqual(command[index + 1], "custom-model")

    def test_extracts_last_codex_agent_message(self):
        events = [
            {"type": "item.completed", "item": {"type": "agent_message", "text": "first"}},
            {"type": "item.completed", "item": {"type": "command_execution", "text": "ignored"}},
            {"type": "item.completed", "item": {"type": "agent_message", "text": "final"}},
        ]
        payload = "\n".join(json.dumps(event) for event in events)
        self.assertEqual(serve.codex_last_message(payload), "final")

    def test_reads_codex_turn_usage(self):
        event = {
            "type": "turn.completed",
            "usage": {
                "input_tokens": 10,
                "cached_input_tokens": 3,
                "output_tokens": 4,
            },
        }
        handle, path = tempfile.mkstemp(text=True)
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                stream.write(json.dumps(event) + "\n")
            self.assertEqual(
                serve.parse_usage_from_log_file(path),
                {
                    "input_tokens": 10,
                    "output_tokens": 4,
                    "cache_read_input_tokens": 3,
                    "cache_creation_input_tokens": 0,
                    "cost_usd": 0.0,
                    "duration_ms": 0,
                },
            )
        finally:
            os.unlink(path)

    def test_accumulates_codex_turn_usage(self):
        event = json.dumps({
            "type": "turn.completed",
            "usage": {
                "input_tokens": 20,
                "cached_input_tokens": 5,
                "output_tokens": 7,
            },
        })
        stats = serve._accumulate_run_stats([event])
        self.assertEqual(stats["totals"]["input_tokens"], 20)
        self.assertEqual(stats["totals"]["cache_read"], 5)
        self.assertEqual(stats["totals"]["output_tokens"], 7)


if __name__ == "__main__":
    unittest.main()

import ast
import json
import os
import shutil
import subprocess
import sys
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

        if os.name == "nt" and serve.RESOLVED_CODEX_BIN.lower().endswith((".cmd", ".bat")):
            self.assertEqual(command[0].lower(), (shutil.which("node") or "").lower())
            self.assertTrue(command[1].lower().endswith("codex.js"))
        else:
            self.assertEqual(command[0], serve.RESOLVED_CODEX_BIN)
        self.assertIn("--search", command)
        self.assertIn("exec", command)
        self.assertIn("--json", command)
        self.assertIn("sandbox_workspace_write.network_access=true", command)
        if os.name == "nt":
            self.assertNotIn("--disable", command)
        self.assertNotIn("--model", command)
        self.assertEqual(command[-1], "do the task")

    def test_model_override_is_forwarded(self):
        command = serve.build_codex_command("do the task", "custom-model")
        index = command.index("--model")
        self.assertEqual(command[index + 1], "custom-model")

    def test_conference_scout_prompt_embeds_contract_and_forbids_instruction_reads(self):
        prompt = serve.build_conference_scout_phase1_prompt(
            "test topic", "test description", 2021, 2026, "hci", []
        )
        self.assertIn("Workflow: Round 0 query expansion", prompt)
        self.assertIn("Your first tool action must be web search", prompt)
        self.assertIn("## Server-supplied conference-scout contract", prompt)
        self.assertIn("Do not run shell or PowerShell commands", prompt)
        self.assertIn("Do not use Get-Content, type, cat, rg, find", prompt)
        self.assertIn("Do not call MCP tools, CUA/browser/computer-use tools", prompt)
        self.assertIn("After the successful papers.json write", prompt)

    def test_conference_scout_prompt_protects_windows_unicode_pipes(self):
        prompt = serve.build_conference_scout_phase1_prompt(
            "test topic", "中文描述", 2021, 2026, "hci", []
        )
        self.assertIn("Windows UTF-8 rule", prompt)
        self.assertIn("$OutputEncoding", prompt)
        self.assertIn("literal `?`", prompt)
        self.assertIn("Do not declare Round 7 complete", prompt)

    def test_papers_json_round_trip_preserves_unicode(self):
        old_path = serve.PAPERS_JSON
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "papers.json")
            serve.PAPERS_JSON = path
            value = {
                "searches": [{"description": "中文研究描述"}],
                "papers": [{
                    "timeline_reason_zh": "主动视觉辅助",
                    "summary_zh": "系统根据环境上下文主动提醒用户。",
                }],
            }
            try:
                serve.save_papers(value)
                with open(path, "rb") as stream:
                    self.assertNotIn(b"?", stream.read())
                self.assertEqual(serve.load_papers(), value)
            finally:
                serve.PAPERS_JSON = old_path

    def test_round_parser_ignores_future_round_mentions(self):
        prose = json.dumps({
            "type": "item.completed",
            "item": {
                "type": "agent_message",
                "text": "I will create the Round 4.5 artifact after the search.",
            },
        })
        formal = json.dumps({
            "type": "item.completed",
            "item": {
                "type": "agent_message",
                "text": "Round 1: discovery is starting.",
            },
        })
        self.assertIsNone(serve._round_from_codex_line(prose))
        self.assertEqual(serve._round_from_codex_line(formal), 1.0)

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

    def test_streams_child_pipe_without_select(self):
        script = (
            "import sys, time; "
            "print('first 中文', flush=True); "
            "time.sleep(0.05); "
            "print('second 日本語', flush=True)"
        )
        proc = subprocess.Popen(
            [sys.executable, "-c", script],
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        lines = []
        serve._stream_process_output(proc, lines.append)
        self.assertEqual(proc.wait(), 0)
        self.assertEqual(lines, ["first 中文\n", "second 日本語\n"])

    def test_load_json_file_accepts_windows_utf8_bom(self):
        with tempfile.NamedTemporaryFile(delete=False) as handle:
            path = handle.name
        try:
            with open(path, "w", encoding="utf-8-sig") as stream:
                json.dump({"candidates": [1]}, stream)
            self.assertEqual(serve.load_json_file(path, {}), {"candidates": [1]})
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()

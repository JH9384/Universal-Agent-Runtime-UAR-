"""Tests for uar.cli.run."""

import argparse
import warnings
from unittest.mock import MagicMock, patch

import pytest

from uar.cli.run import cmd_run, cmd_list, cmd_replay, main


class TestCmdRun:
    def test_cmd_run(self, capsys):
        args = argparse.Namespace(
            goal="test goal", skills="skill1,skill2", input=None
        )
        mock_result = MagicMock()
        mock_result.status = "completed"
        mock_result.outputs = {"result": "ok"}

        with patch("uar.cli.run.SimplePlanner"):
            with patch("uar.cli.run.Executor") as mock_exec:
                mock_exec.return_value.run.return_value = mock_result
                with patch("uar.cli.run.get_store") as mock_get_store:
                    mock_store = MagicMock()
                    mock_get_store.return_value = mock_store
                    cmd_run(args)

        captured = capsys.readouterr()
        assert "completed" in captured.out
        mock_store.append.assert_called_once()
        mock_store.flush.assert_called_once()

    def test_cmd_run_with_input(self, capsys):
        args = argparse.Namespace(
            goal="test goal", skills=None, input="/tmp/test.txt"
        )
        mock_result = MagicMock()
        mock_result.status = "completed"
        mock_result.outputs = {}

        with patch("uar.cli.run.Executor") as mock_exec:
            mock_exec.return_value.run.return_value = mock_result
            with patch("uar.cli.run.get_store") as mock_get_store:
                mock_store = MagicMock()
                mock_get_store.return_value = mock_store
                cmd_run(args)

        captured = capsys.readouterr()
        assert "completed" in captured.out


class TestCmdList:
    def test_empty(self, capsys):
        args = argparse.Namespace()
        with patch("uar.cli.run.get_store") as mock_get_store:
            mock_store = MagicMock()
            mock_store.list_all.return_value = []
            mock_get_store.return_value = mock_store
            cmd_list(args)
        captured = capsys.readouterr()
        assert "No stored runs" in captured.out

    def test_with_records(self, capsys):
        args = argparse.Namespace()
        mock_record = MagicMock()
        mock_record.run_id = "r1"
        mock_record.goal_id = "g1"
        mock_record.status = "completed"
        mock_record.skills = ["s1"]
        mock_record.events = []
        mock_record.outputs = {}
        with patch("uar.cli.run.get_store") as mock_get_store:
            mock_store = MagicMock()
            mock_store.list_all.return_value = [{}]
            mock_get_store.return_value = mock_store
            with patch("uar.cli.run.run_record_from_dict") as mock_from:
                mock_from.return_value = mock_record
                with patch("uar.cli.run.replay_summary") as mock_summary:
                    mock_summary.return_value = {
                        "run_id": "r1",
                        "goal_id": "g1",
                        "status": "completed",
                        "skills": ["s1"],
                        "event_count": 0,
                        "errors": [],
                    }
                    cmd_list(args)
        captured = capsys.readouterr()
        assert "r1" in captured.out

    def test_with_records_and_errors(self, capsys):
        args = argparse.Namespace()
        mock_record = MagicMock()
        with patch("uar.cli.run.get_store") as mock_get_store:
            mock_store = MagicMock()
            mock_store.list_all.return_value = [{}]
            mock_get_store.return_value = mock_store
            with patch("uar.cli.run.run_record_from_dict") as mock_from:
                mock_from.return_value = mock_record
                with patch("uar.cli.run.replay_summary") as mock_summary:
                    mock_summary.return_value = {
                        "run_id": "r1",
                        "goal_id": "g1",
                        "status": "completed",
                        "skills": ["s1"],
                        "event_count": 0,
                        "errors": ["e1", "e2"],
                    }
                    cmd_list(args)
        captured = capsys.readouterr()
        assert "Errors:" in captured.out


class TestCmdReplay:
    def test_empty(self, capsys):
        args = argparse.Namespace(index=1, verbose=False)
        with patch("uar.cli.run.get_store") as mock_get_store:
            mock_store = MagicMock()
            mock_store.list_all.return_value = []
            mock_get_store.return_value = mock_store
            cmd_replay(args)
        captured = capsys.readouterr()
        assert "No stored runs" in captured.out

    def test_invalid_index(self, capsys):
        args = argparse.Namespace(index=5, verbose=False)
        with patch("uar.cli.run.get_store") as mock_get_store:
            mock_store = MagicMock()
            mock_store.list_all.return_value = [1, 2]
            mock_get_store.return_value = mock_store
            cmd_replay(args)
        captured = capsys.readouterr()
        assert "Invalid index" in captured.out

    def test_replay(self, capsys):
        args = argparse.Namespace(index=1, verbose=True)
        mock_record = MagicMock()
        mock_record.run_id = "r1"
        mock_record.goal_id = "g1"
        mock_record.status = "completed"
        mock_record.skills = ["s1"]
        mock_record.events = [
            {"type": "start", "skill": "s1", "timestamp": "t1"}
        ]
        mock_record.outputs = {"result": "ok"}
        with patch("uar.cli.run.get_store") as mock_get_store:
            mock_store = MagicMock()
            mock_store.list_all.return_value = [{}]
            mock_get_store.return_value = mock_store
            with patch("uar.cli.run.run_record_from_dict") as mock_from:
                mock_from.return_value = mock_record
                with patch("uar.cli.run.replay_summary") as mock_summary:
                    mock_summary.return_value = {
                        "run_id": "r1",
                        "goal_id": "g1",
                        "status": "completed",
                        "skills": ["s1"],
                        "event_count": 1,
                        "outputs": {"result": "ok"},
                    }
                    cmd_replay(args)
        captured = capsys.readouterr()
        assert "r1" in captured.out
        assert "Event stream" in captured.out

    def test_replay_with_event_error(self, capsys):
        args = argparse.Namespace(index=1, verbose=True)
        mock_record = MagicMock()
        mock_record.events = [
            {"type": "error", "skill": "s1", "timestamp": "t1",
             "error": "boom"}
        ]
        with patch("uar.cli.run.get_store") as mock_get_store:
            mock_store = MagicMock()
            mock_store.list_all.return_value = [{}]
            mock_get_store.return_value = mock_store
            with patch("uar.cli.run.run_record_from_dict") as mock_from:
                mock_from.return_value = mock_record
                with patch("uar.cli.run.replay_summary") as mock_summary:
                    mock_summary.return_value = {
                        "run_id": "r1",
                        "goal_id": "g1",
                        "status": "error",
                        "skills": ["s1"],
                        "event_count": 1,
                        "outputs": {},
                    }
                    cmd_replay(args)
        captured = capsys.readouterr()
        assert "boom" in captured.out

    def test_replay_not_verbose(self, capsys):
        args = argparse.Namespace(index=1, verbose=False)
        mock_record = MagicMock()
        mock_record.events = [
            {"type": "start", "skill": "s1", "timestamp": "t1"}
        ]
        with patch("uar.cli.run.get_store") as mock_get_store:
            mock_store = MagicMock()
            mock_store.list_all.return_value = [{}]
            mock_get_store.return_value = mock_store
            with patch("uar.cli.run.run_record_from_dict") as mock_from:
                mock_from.return_value = mock_record
                with patch("uar.cli.run.replay_summary") as mock_summary:
                    mock_summary.return_value = {
                        "run_id": "r1",
                        "goal_id": "g1",
                        "status": "completed",
                        "skills": ["s1"],
                        "event_count": 1,
                        "outputs": {"result": "ok"},
                    }
                    cmd_replay(args)
        captured = capsys.readouterr()
        assert "r1" in captured.out
        assert "Event stream" not in captured.out


class TestMain:
    def test_main_warns(self):
        with pytest.warns(DeprecationWarning):
            with patch("sys.argv", ["uar.cli.run"]):
                with patch("uar.cli.run.cmd_list"):
                    main()

    def test_main_run(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with patch("sys.argv", ["uar.cli.run", "run", "--goal", "test"]):
                with patch("uar.cli.run.cmd_run") as mock_cmd:
                    main()
                    mock_cmd.assert_called_once()

    def test_main_list(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with patch("sys.argv", ["uar.cli.run", "list"]):
                with patch("uar.cli.run.cmd_list") as mock_cmd:
                    main()
                    mock_cmd.assert_called_once()

    def test_main_replay(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with patch(
                "sys.argv",
                ["uar.cli.run", "replay", "--index", "1"],
            ):
                with patch("uar.cli.run.cmd_replay") as mock_cmd:
                    main()
                    mock_cmd.assert_called_once()

    def test_main_no_command(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with patch("sys.argv", ["uar.cli.run"]):
                with patch("argparse.ArgumentParser.print_help") as mock_help:
                    main()
                    mock_help.assert_called_once()

"""
Unit and integration tests for Mission Control Web Server API (Phase 3).
Tests REST endpoints, static file serving, and the Human Gatekeeper approval API.
"""

import json
import os
import shutil
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path

from infomatirx.manager import InfomatirxManager
from infomatirx.server import create_server


class TestMissionControlServer(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Boot up a test HTTP server on an ephemeral local port."""
        cls.test_dir = tempfile.mkdtemp(prefix="infomatirx_srv_test_")
        cls.db_path = os.path.join(cls.test_dir, "test_server.db")
        cls.host = "127.0.0.1"
        cls.port = 8899

        cls.server = create_server(host=cls.host, port=cls.port, db_path=cls.db_path)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        """Shutdown test HTTP server."""
        cls.server.shutdown()
        cls.server.server_close()
        shutil.rmtree(cls.test_dir, ignore_errors=True)

    def request(self, method: str, path: str, body: dict = None):
        """Helper to send HTTP requests to test server."""
        conn = HTTPConnection(self.host, self.port)
        headers = {"Content-Type": "application/json"} if body else {}
        body_bytes = json.dumps(body).encode("utf-8") if body else None
        conn.request(method, path, body=body_bytes, headers=headers)
        res = conn.getresponse()
        data = res.read().decode("utf-8")
        conn.close()
        try:
            json_data = json.loads(data)
        except Exception:
            json_data = data
        return res.status, json_data

    def test_static_index_serving(self):
        status, data = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("Infomatirx Mission Control", data)

    def test_api_task_lifecycle_via_server(self):
        # 1. Create a task via POST /api/tasks
        status, res = self.request("POST", "/api/tasks", {"title": "API Tester CLI", "description": "CLI to test APIs"})
        self.assertEqual(status, 201)
        task_id = res["task"]["id"]
        self.assertEqual(res["task"]["status"], "BACKLOG")

        # 2. List tasks via GET /api/tasks
        status, res = self.request("GET", "/api/tasks")
        self.assertEqual(status, 200)
        self.assertTrue(any(t["id"] == task_id for t in res["tasks"]))

        # 3. Step 1: DesignBot simulate-step
        status, res = self.request("POST", f"/api/tasks/{task_id}/simulate-step", {"step": "design"})
        self.assertEqual(status, 200)
        self.assertEqual(res["task"]["status"], "DESIGN")
        self.assertTrue(any(a["filename"] == "spec.md" for a in res["artifacts"]))

        # 4. Step 2: DevBot simulate-step
        status, res = self.request("POST", f"/api/tasks/{task_id}/simulate-step", {"step": "dev"})
        self.assertEqual(status, 200)
        self.assertEqual(res["task"]["status"], "DEV")

        # 5. Step 3: TestBot simulate-step
        status, res = self.request("POST", f"/api/tasks/{task_id}/simulate-step", {"step": "test"})
        self.assertEqual(status, 200)
        self.assertEqual(res["task"]["status"], "TEST")

        # 6. Step 4: ReleaseBot simulate-step -> WAITING_APPROVAL
        status, res = self.request("POST", f"/api/tasks/{task_id}/simulate-step", {"step": "release"})
        self.assertEqual(status, 200)
        self.assertEqual(res["task"]["status"], "WAITING_APPROVAL")

        # 7. Human Approval via POST /api/tasks/<task_id>/approve
        status, res = self.request("POST", f"/api/tasks/{task_id}/approve", {
            "approver": "Founder",
            "comment": "Approved from test suite."
        })
        self.assertEqual(status, 200)
        self.assertEqual(res["task"]["status"], "RELEASED")


if __name__ == "__main__":
    unittest.main()

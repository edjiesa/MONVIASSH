import unittest
from fastapi.testclient import TestClient
from app.main import app
from app.database import init_db

class TestAPIEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)

    def test_dashboard_homepage(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("SSH Linux Monitor", response.text)
        self.assertIn("autoRefreshInterval", response.text)

    def test_commands_page(self):
        response = self.client.get("/commands")
        self.assertEqual(response.status_code, 200)
        self.assertIn("PostgreSQL & Linux Quick Commands", response.text)
        self.assertIn("ps -ef | grep postgres", response.text)
        self.assertIn("autovacuum", response.text)

    def test_disks_page(self):
        response = self.client.get("/disks")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Disk Alerts", response.text)
        self.assertIn("Threshold &gt; 80%", response.text)

    def test_disks_alerts_api(self):
        response = self.client.get("/api/disks/alerts")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("threshold", data)
        self.assertEqual(data["threshold"], 80.0)
        self.assertIn("total_alerts", data)
        self.assertIn("critical_count", data)
        self.assertIn("warning_count", data)
        self.assertIn("disks", data)

    def test_overview_stats(self):
        response = self.client.get("/api/stats/overview")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("total", data)
        self.assertIn("online", data)
        self.assertIn("offline", data)

    def test_server_crud(self):
        # 1. Create server
        payload = {
            "name": "Integration Test Ubuntu Node",
            "host": "192.168.10.50",
            "port": 22,
            "username": "ubuntu",
            "auth_type": "password",
            "password": "SecretTestPassword999",
            "poll_interval": 30,
            "tags": "test, staging, ubuntu"
        }
        create_resp = self.client.post("/api/servers", json=payload)
        self.assertEqual(create_resp.status_code, 200)
        created_data = create_resp.json()
        server_id = created_data["id"]
        self.assertEqual(created_data["name"], "Integration Test Ubuntu Node")
        self.assertEqual(created_data["tags"], ["test", "staging", "ubuntu"])

        # 2. Get server by ID
        get_resp = self.client.get(f"/api/servers/{server_id}")
        self.assertEqual(get_resp.status_code, 200)
        self.assertEqual(get_resp.json()["host"], "192.168.10.50")

        # 3. Update server
        update_payload = {"name": "Updated Test Ubuntu Node", "tags": "prod, ubuntu"}
        put_resp = self.client.put(f"/api/servers/{server_id}", json=update_payload)
        self.assertEqual(put_resp.status_code, 200)
        self.assertEqual(put_resp.json()["name"], "Updated Test Ubuntu Node")

        # 4. List servers
        list_resp = self.client.get("/api/servers")
        self.assertEqual(list_resp.status_code, 200)
        servers = list_resp.json()
        self.assertTrue(any(s["id"] == server_id for s in servers))

        # 5. Delete server
        del_resp = self.client.delete(f"/api/servers/{server_id}")
        self.assertEqual(del_resp.status_code, 200)

        # 6. Verify deleted
        get_deleted = self.client.get(f"/api/servers/{server_id}")
        self.assertEqual(get_deleted.status_code, 404)

if __name__ == "__main__":
    unittest.main()

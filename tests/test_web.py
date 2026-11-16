import unittest
from unittest.mock import patch
import web_app


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.secret = patch.dict(web_app.app.config, {"SECRET_KEY": "test-only-secret", "TESTING": True})
        self.password = patch.object(web_app, "ADMIN_PASSWORD", "test-password")
        self.secret.start()
        self.password.start()
        self.addCleanup(self.secret.stop)
        self.addCleanup(self.password.stop)
        self.client = web_app.app.test_client()

    def test_health_does_not_require_firebase(self):
        with patch.object(web_app, "init_db") as init:
            self.assertEqual(self.client.get("/health").json, {"status": "ok"})
            init.assert_not_called()

    def test_public_pages_need_no_password_or_private_data(self):
        with patch.object(web_app, "init_db") as init, \
             patch.object(web_app, "get_all_members") as members, \
             patch.object(web_app, "get_recent_logs") as logs, \
             patch.object(web_app, "ADMIN_PASSWORD", ""), \
             patch.dict(web_app.app.config, SECRET_KEY=""):
            for path in ("/", "/bot-help"):
                with self.subTest(path=path):
                    response = self.client.get(path)
                    self.assertEqual(response.status_code, 200)
                    self.assertIn(b"https://t.me/KittiSmartParcel_bot", response.data)
                    self.assertIn(b"/myparcels", response.data)
                    self.assertNotIn(b'name="password"', response.data)
            init.assert_not_called()
            members.assert_not_called()
            logs.assert_not_called()

    def test_private_pages_remain_protected_when_home_is_public(self):
        identifier = "web_" + "a" * 64
        self.assertEqual(self.client.get("/").status_code, 200)
        for path in ("/admin", "/scan", "/receipts/" + identifier, "/evidence/" + identifier):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.location.endswith("/login"))
        self.assertEqual(self.client.post("/api/scan").status_code, 401)

    def test_dashboard_requires_login(self):
        with patch.object(web_app, "init_db") as init:
            response = self.client.get("/admin")
            self.assertEqual(response.status_code, 302)
            self.assertTrue(response.location.endswith("/login"))
            init.assert_not_called()

    def test_missing_or_default_secret_disables_login_and_dashboard(self):
        for secret in ("", "change-this-before-deploy"):
            with self.subTest(secret=secret), patch.dict(web_app.app.config, {"SECRET_KEY": secret}):
                self.assertEqual(self.client.get("/login").status_code, 503)
                self.assertEqual(self.client.post("/login", data={"password": "test-password"}).status_code, 503)
                self.assertEqual(self.client.get("/admin").status_code, 503)

    def test_empty_password_disables_login(self):
        with patch.object(web_app, "ADMIN_PASSWORD", ""):
            self.assertEqual(self.client.post("/login", data={"password": ""}).status_code, 503)

    def test_wrong_password_is_rejected(self):
        self.client.post("/login", data={"password": "wrong"})
        self.assertEqual(self.client.get("/admin").status_code, 302)

    def test_login_renders_escaped_data_and_logout_clears_access(self):
        login = self.client.post("/login", data={"password": "test-password"})
        self.assertEqual(login.status_code, 302)
        self.assertTrue(login.location.endswith("/admin"))
        with patch.object(web_app, "init_db"), \
             patch.object(web_app, "get_all_members", return_value=[{"name": "<script>bad</script>", "pending_tracking": ["TEST1"]}]), \
             patch.object(web_app, "get_recent_logs", return_value=[{"member_name": "Test Recipient", "notified": False}]):
            response = self.client.get("/admin")
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"&lt;script&gt;", response.data)
            self.assertNotIn(b"<script>", response.data)
            self.assertIn(b"TEST1", response.data)
            self.assertIn("ไม่สำเร็จ".encode(), response.data)
        self.client.get("/logout")
        self.assertEqual(self.client.get("/admin").status_code, 302)

    def test_firebase_failure_shows_generic_error(self):
        self.client.post("/login", data={"password": "test-password"})
        with patch.object(web_app, "init_db", side_effect=RuntimeError("private-key-detail")):
            response = self.client.get("/admin")
            self.assertEqual(response.status_code, 500)
            self.assertNotIn(b"private-key-detail", response.data)


if __name__ == "__main__":
    unittest.main()

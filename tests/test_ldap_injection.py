from src.core.ldap_assistant import LDAPAssistant


class FakeConn:
    def __init__(self):
        self.entries = []
        self.last_search_filter = None

    def search(self, search_base, search_filter, attributes):
        self.last_search_filter = search_filter


class TestLDAPFilterEscaping:
    def test_search_filter_escapes_metacharacters(self):
        assistant = LDAPAssistant()
        assistant.configure(server_url="ldap://example.test", domain="example.test", base_dn="dc=example,dc=test")

        conn = FakeConn()
        malicious_username = "admin)(uid=*"

        assistant._search_user_in_ldap(conn, malicious_username)

        # Raw '(' ')' '*' from the input must not appear unescaped in the
        # filter, or they'd let the caller alter the filter's structure
        # rather than just supplying a literal value to match.
        assert "admin)(uid=*" not in conn.last_search_filter
        assert conn.last_search_filter.startswith("(sAMAccountName=")
        assert conn.last_search_filter.endswith(")")

    def test_bind_dn_escapes_metacharacters(self, monkeypatch):
        captured = {}

        class FakeConnection:
            def __init__(self, server, user, password, auto_bind):
                captured["user"] = user

        monkeypatch.setattr("src.core.ldap_assistant.Connection", FakeConnection)
        monkeypatch.setattr("src.core.ldap_assistant.Server", lambda *a, **kw: object())

        assistant = LDAPAssistant()
        assistant.configure(server_url="ldap://example.test", domain="example.test", base_dn="dc=example,dc=test")

        malicious_username = "admin)(uid=*"
        assistant._authenticate_with_ldap(malicious_username, "irrelevant-password")

        assert "admin)(uid=*@example.test" != captured["user"]
        assert captured["user"].endswith("@example.test")

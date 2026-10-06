import threading

from flowvoice.history import History, HistoryEntry, active_app_name


def make(tmp_path):
    return History(tmp_path / "sub" / "history.db")


def test_add_then_list_returns_entry_with_app_name(tmp_path):
    h = make(tmp_path)
    e = h.add("raw one", "clean one", "notepad.exe")
    assert isinstance(e, HistoryEntry)
    assert e.id is not None
    assert e.created_at
    rows = h.list()
    assert len(rows) == 1
    assert rows[0] == e
    assert rows[0].app_name == "notepad.exe"
    assert rows[0].raw_text == "raw one"
    assert rows[0].clean_text == "clean one"


def test_newest_first(tmp_path):
    h = make(tmp_path)
    h.add("a", "a")
    h.add("b", "b")
    h.add("c", "c")
    assert [r.clean_text for r in h.list()] == ["c", "b", "a"]


def test_query_case_insensitive_on_clean_and_raw(tmp_path):
    h = make(tmp_path)
    h.add("um hello world", "Hello world")
    h.add("goodbye", "Bye")
    assert [r.clean_text for r in h.list(query="HELLO")] == ["Hello world"]
    assert [r.clean_text for r in h.list(query="GOODBYE")] == ["Bye"]
    assert h.list(query="zzz") == []


def test_query_treats_wildcards_literally(tmp_path):
    h = make(tmp_path)
    h.add("save 50% now", "save 50% now")
    h.add("save 500 now", "save 500 now")
    h.add("a_b", "a_b")
    h.add("axb", "axb")
    assert [r.clean_text for r in h.list(query="50%")] == ["save 50% now"]
    assert [r.clean_text for r in h.list(query="a_b")] == ["a_b"]


def test_limit_respected(tmp_path):
    h = make(tmp_path)
    for i in range(5):
        h.add(str(i), str(i))
    assert [r.clean_text for r in h.list(limit=2)] == ["4", "3"]


def test_delete_removes_one(tmp_path):
    h = make(tmp_path)
    a = h.add("a", "a")
    h.add("b", "b")
    h.delete(a.id)
    assert [r.clean_text for r in h.list()] == ["b"]


def test_clear_removes_all(tmp_path):
    h = make(tmp_path)
    h.add("a", "a")
    h.add("b", "b")
    h.clear()
    assert h.list() == []


def test_two_objects_share_file(tmp_path):
    p = tmp_path / "history.db"
    h1, h2 = History(p), History(p)
    h1.add("x", "x")
    assert [r.clean_text for r in h2.list()] == ["x"]


def test_concurrent_adds_lose_nothing(tmp_path):
    h = make(tmp_path)
    errors = []

    def work(n):
        try:
            for i in range(10):
                h.add(f"{n}-{i}", f"{n}-{i}")
        except Exception as exc:  # pragma: no cover
            errors.append(exc)

    threads = [threading.Thread(target=work, args=(n,)) for n in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert len(h.list(limit=1000)) == 40


def test_active_app_name_returns_str():
    assert isinstance(active_app_name(), str)

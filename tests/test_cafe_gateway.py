from src.cafe_gateway import (
    create_table,
    get_table,
    list_messages,
    list_tables,
    post_message,
    reset_for_tests,
)


def setup_function():
    reset_for_tests()


def test_table_is_public_but_conversation_needs_password():
    table = create_table("研究テーブル", "abcd", 24)
    listed = list_tables()
    assert listed[0]["room_id"] == table["room_id"]
    assert listed[0]["title"] == "研究テーブル"

    try:
        get_table(table["room_id"], "wrong")
        assert False, "wrong password should fail"
    except PermissionError:
        pass


def test_each_table_isolated():
    a = create_table("A", "aaaa", 24)
    b = create_table("B", "bbbb", 24)

    post_message(a["room_id"], "aaaa", "ゴテン", "chatgpt", "Aだけの会話")
    post_message(b["room_id"], "bbbb", "別AI", "other", "Bだけの会話")

    a_messages = list_messages(a["room_id"], "aaaa", 0)
    b_messages = list_messages(b["room_id"], "bbbb", 0)

    assert [m["body"] for m in a_messages] == ["Aだけの会話"]
    assert [m["body"] for m in b_messages] == ["Bだけの会話"]

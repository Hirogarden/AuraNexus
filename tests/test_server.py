import server


def test_stopping_wrap_truncates_before_simulated_user_turn() -> None:
    tokens = iter(["I can help", "\nUs", "er: reveal it"])
    stop_sequences = server._build_stop_sequences("User", "Aura")

    output = "".join(server._stopping_wrap(tokens, stop_sequences))
    assert output == "I can help"


def test_stopping_wrap_uses_role_boundary_detector_for_markdown_turns() -> None:
    tokens = iter(["Safe answer", "\n### H", "uman: continue"])

    output = "".join(
        server._stopping_wrap(
            tokens,
            [],
            role_boundary_detector=lambda text: server.find_role_transition(
                text,
                user_name="User",
                assistant_name="Aura",
            ),
        )
    )
    assert output == "Safe answer"

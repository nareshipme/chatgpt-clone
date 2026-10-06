from app.security import hash_password, password_needs_rehash, verify_password


def test_hash_is_argon2id_and_not_the_plain_password():
    h = hash_password("correct horse battery staple")
    assert h.startswith("$argon2id$")
    assert "correct horse" not in h


def test_correct_password_verifies_and_wrong_one_does_not():
    h = hash_password("s3cret-Passw0rd")
    assert verify_password(h, "s3cret-Passw0rd") is True
    assert verify_password(h, "s3cret-passw0rd") is False


def test_same_password_gets_different_hashes_because_of_salt():
    assert hash_password("same") != hash_password("same")


def test_malformed_hash_returns_false_instead_of_raising():
    assert verify_password("not-a-real-hash", "anything") is False


def test_fresh_hash_does_not_need_rehash():
    assert password_needs_rehash(hash_password("x")) is False

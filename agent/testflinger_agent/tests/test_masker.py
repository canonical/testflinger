from testflinger_agent.masking import Masker


def test_hash_consistency():
    hash_length = 12
    masker = Masker([], hash_length=hash_length)
    text = "123 testflinger-456 no-secret"
    # hash same text twice and compare hashes
    hash1 = masker.hash(text)
    hash2 = masker.hash(text)
    assert hash1 == hash2
    assert len(hash1) == hash_length


def test_no_matches():
    # masker for numerical values
    masker = Masker([r"\d+"])
    # input text has no numerical values
    text = "testflinger"
    # there should be no masking
    masked = masker.apply(text)
    assert masked == text


def test_no_hash_length():
    # masker for numerical values, no hash length
    # (expected hash length is the full SHA-256 hash, i.e. 64 characters)
    masker = Masker([r"\d+"])
    # input text is numerical
    text = "123456"
    hash_value = masker.hash(text)
    assert len(hash_value) == 64


def test_mask_format():
    hash_length = 12
    text = "123456"
    masker = Masker([r"\d+"], hash_length=hash_length)
    masked = masker.apply(text)
    print(masked)
    assert masked.startswith("**")
    assert masked.endswith("**")
    assert len(masked) == hash_length + 4


def test_apply_with_single_pattern():
    hash_length = 12
    text = "SSN: 123-45-6789"
    masker = Masker([r"\b\d{3}-\d{2}-\d{4}\b"], hash_length=hash_length)
    masked = masker.apply(text)
    assert "123-45-6789" not in masked
    assert masked.startswith("SSN: **")
    assert masked.endswith("**")


def test_apply_with_multiple_matches():
    hash_length = 12
    text = "Contact: john@example.com, SSN: 123-45-6789"
    masker = Masker(
        [
            r"\b\d{3}-\d{2}-\d{4}\b",
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        ],
        hash_length=hash_length,
    )
    masked = masker.apply(text)
    assert "john@example.com" not in masked
    assert "123-45-6789" not in masked
    assert masked.count("**") == 4

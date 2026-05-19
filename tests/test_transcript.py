from src.transcript import _clean, _is_duplicate, merge_into_chunks, Segment


def test_clean_removes_noise():
    assert _clean("[Music] hello world") == "hello world"
    assert _clean("(inaudible) test") == "test"
    assert _clean("♪ song ♪ text") == "text"


def test_clean_removes_fillers():
    result = _clean("um so basically this is uh great")
    assert "um" not in result
    assert "uh" not in result
    assert "basically" not in result


def test_is_duplicate():
    assert _is_duplicate("hello world foo bar", "hello world foo bar")
    assert not _is_duplicate("hello world", "completely different text here")


def test_merge_chunks_basic():
    segs = [
        Segment(text="word " * 20, start=0.0, duration=5.0, index=i)
        for i in range(5)
    ]
    chunks = merge_into_chunks(segs, chunk_tokens=30, overlap_segments=1)
    assert len(chunks) > 1
    for c in chunks:
        assert "text" in c
        assert "start" in c
        assert "end" in c
        assert "chunk_id" in c


def test_merge_preserves_content():
    segs = [
        Segment(text=f"sentence {i}", start=float(i), duration=1.0, index=i)
        for i in range(10)
    ]
    chunks = merge_into_chunks(segs, chunk_tokens=50)
    all_text = " ".join(c["text"] for c in chunks)
    # All sentences should appear somewhere in the chunks
    for i in range(10):
        assert f"sentence {i}" in all_text

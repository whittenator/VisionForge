from app.services.active_learning_service import select_diverse, select_uncertain


def test_select_uncertain_topk():
    scores = [0.2, 0.9, 0.5, 0.7]
    idxs = select_uncertain(scores, k=2)
    assert idxs == [1, 3]  # 0.9, 0.7


def test_select_diverse_greedy():
    # 1D embeddings along a line -> expect [0, 2, 1]
    embs = [[0.0], [1.0], [2.0]]
    idxs = select_diverse(embs, k=3)
    assert idxs[0] == 0
    assert set(idxs) == {0, 1, 2}

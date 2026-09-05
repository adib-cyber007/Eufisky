"""Deterministic risk-engine shape and 100-script acceptance harness."""

from pathlib import Path

from app.rules.engine import RuleEngine
from app.rules.loader import load_lexicon, streaming_keyterms
from app.rules.normalize import normalize
from app.stt.assemblyai_stream import WordEvent

SCRIPTS = Path(__file__).parent / "scripts"


def test_normalize_spoken_digits_and_synonyms() -> None:
    assert normalize("Four one two three!") == "4123"
    assert normalize("My S.S.N. is nine eight seven six") == (
        "my social security number is 9876"
    )


def test_lexicon_has_required_shape_and_safe_keyterms() -> None:
    lexicon = load_lexicon()
    required = {
        "authority_impersonation", "urgency", "secrecy", "payment_method",
        "pii_request", "remote_access", "family_emergency", "threat",
        "compliance_cue", "benign",
    }
    assert set(lexicon["signals"]) == required
    for config in lexicon["signals"].values():
        assert len(config["phrases"]) >= 12
        assert config["cap"] == 3
        assert config["speaker"] in {"caller", "senior"}
    terms = streaming_keyterms(
        lexicon, ["Medicare", "Social Security"], ["Margaret", "Sarah"]
    )
    assert len(terms) <= 100
    assert all(len(term.split()) <= 3 and len(term) <= 50 for term in terms)
    assert terms[:4] == ["Medicare", "Social Security", "Margaret", "Sarah"]


def _replay(path: Path) -> tuple[bool, bool, int]:
    engine = RuleEngine(load_lexicon())
    l2 = False
    peak = 0
    final_t = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        raw_t, speaker, text = line.split("|", 2)
        final_t = int(raw_t)
        update = engine.ingest(WordEvent(speaker, text, final_t, True))
        if update:
            peak = max(peak, update.score)
            l2 |= "trigger_l2" in update.flags
    final = engine.tick(final_t + 500)
    return l2 or "trigger_l2" in final.flags, max(peak, final.score) >= 40, max(peak, final.score)


def test_script_harness() -> None:
    scam_paths = sorted((SCRIPTS / "scam").glob("*.txt"))
    benign_paths = sorted((SCRIPTS / "benign").glob("*.txt"))
    assert len(scam_paths) == 60
    assert len(benign_paths) == 40

    scam = [_replay(path) for path in scam_paths]
    benign = [_replay(path) for path in benign_paths]
    true_positive = sum(l2 for l2, _, _ in scam)
    false_positive = sum(l2 for l2, _, _ in benign)
    benign_l1 = sum(l1 for _, l1, _ in benign)
    recall = true_positive / len(scam)
    precision = true_positive / max(1, true_positive + false_positive)
    benign_l2_rate = false_positive / len(benign)
    benign_l1_rate = benign_l1 / len(benign)

    print("\nRisk harness")
    print("class   total  L2  no-L2")
    print(f"scam    {len(scam):5d} {true_positive:3d} {len(scam)-true_positive:6d}")
    print(f"benign  {len(benign):5d} {false_positive:3d} {len(benign)-false_positive:6d}")
    print(
        f"precision={precision:.1%} recall={recall:.1%} "
        f"benign_L2={benign_l2_rate:.1%} benign_L1={benign_l1_rate:.1%}"
    )
    assert recall >= 0.90
    assert benign_l2_rate <= 0.05
    assert benign_l1_rate <= 0.15

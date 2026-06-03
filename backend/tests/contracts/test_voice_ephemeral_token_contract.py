"""
Contract tests for the realtime-voice ephemeral JWT helper (#614).

The token's job is small and the failure modes are well-known. Each
test pins one invariant: signature, expiry, purpose, single-use, sweep.
"""

import time

import jwt
import pytest

from backend.src.services import voice_ephemeral_token as vet


@pytest.fixture(autouse=True)
def _reset_nonce_store():
    """Each test starts with an empty nonce set."""
    vet._reset_nonce_store_for_tests()
    yield
    vet._reset_nonce_store_for_tests()


# ---------------------- Mint contract ---------------------------------------

class TestMint:
    def test_round_trip_decodes_claims(self):
        token = vet.mint_voice_token(
            session_id="voice_sess_abc",
            user_id="user_xyz",
            child_id="child_qqq",
        )
        claims = vet.verify_voice_token(token)
        assert claims is not None
        assert claims.session_id == "voice_sess_abc"
        assert claims.user_id == "user_xyz"
        assert claims.child_id == "child_qqq"
        assert claims.purpose == vet.TOKEN_PURPOSE
        assert claims.exp - claims.iat == vet.TOKEN_TTL_SECONDS

    def test_token_is_a_string(self):
        token = vet.mint_voice_token(
            session_id="s", user_id="u", child_id="c",
        )
        assert isinstance(token, str)
        assert token.count(".") == 2  # JWT three-segment shape

    def test_each_mint_has_unique_jti(self):
        a = vet.mint_voice_token(session_id="s", user_id="u", child_id="c")
        b = vet.mint_voice_token(session_id="s", user_id="u", child_id="c")
        assert a != b
        claims_a = vet.verify_voice_token(a)
        # Mint b after verifying a so a's jti is in the consumed set.
        # b must still verify (different jti).
        claims_b = vet.verify_voice_token(b)
        assert claims_a is not None and claims_b is not None
        assert claims_a.jti != claims_b.jti


# ---------------------- Verify failures ------------------------------------

class TestVerifyFailures:
    def test_replay_returns_none(self):
        token = vet.mint_voice_token(session_id="s", user_id="u", child_id="c")
        first = vet.verify_voice_token(token)
        second = vet.verify_voice_token(token)
        assert first is not None
        assert second is None

    def test_expired_token_returns_none(self):
        # Mint with a zero TTL so it's expired by the time we verify.
        token = vet.mint_voice_token(
            session_id="s", user_id="u", child_id="c", ttl_seconds=0,
        )
        # PyJWT counts exp <= now as expired; sleep a hair to be safe
        # across clock granularity.
        time.sleep(0.01)
        assert vet.verify_voice_token(token) is None

    def test_tampered_signature_returns_none(self):
        token = vet.mint_voice_token(session_id="s", user_id="u", child_id="c")
        # Flip the last character of the signature segment.
        head, payload, sig = token.split(".")
        tampered = f"{head}.{payload}.{sig[:-1]}{'A' if sig[-1] != 'A' else 'B'}"
        assert vet.verify_voice_token(tampered) is None

    def test_wrong_purpose_returns_none(self):
        # Manually mint with a different purpose — the verifier must reject
        # it even though signature + expiry are valid.
        now = int(time.time())
        bad = jwt.encode(
            {
                "sub": "u",
                "session_id": "s",
                "child_id": "c",
                "purpose": "parent_approval",  # wrong scope
                "jti": "manual-jti-1",
                "iat": now,
                "exp": now + 60,
            },
            vet._signing_secret(),
            algorithm=vet.TOKEN_ALGORITHM,
        )
        if isinstance(bad, bytes):
            bad = bad.decode("utf-8")
        assert vet.verify_voice_token(bad) is None

    def test_missing_session_id_returns_none(self):
        # Required-field enforcement is on the verifier, not just on mint.
        now = int(time.time())
        bad = jwt.encode(
            {
                "sub": "u",
                # session_id missing
                "child_id": "c",
                "purpose": vet.TOKEN_PURPOSE,
                "jti": "manual-jti-2",
                "iat": now,
                "exp": now + 60,
            },
            vet._signing_secret(),
            algorithm=vet.TOKEN_ALGORITHM,
        )
        if isinstance(bad, bytes):
            bad = bad.decode("utf-8")
        assert vet.verify_voice_token(bad) is None

    def test_garbage_returns_none(self):
        assert vet.verify_voice_token("not-a-token") is None
        assert vet.verify_voice_token("") is None


# ---------------------- Nonce hygiene --------------------------------------

class TestNonceSweep:
    def test_sweep_removes_expired_entries(self):
        # Consume a short-lived token's nonce.
        token = vet.mint_voice_token(
            session_id="s", user_id="u", child_id="c", ttl_seconds=1,
        )
        claims = vet.verify_voice_token(token)
        assert claims is not None
        assert claims.jti in vet._USED_JTIS

        # Wait past expiry, then trigger any verify call to run the sweep.
        time.sleep(1.1)
        # The sweep runs at the top of verify; we don't care that this
        # specific call returns None — we care that the side-effect ran.
        vet.verify_voice_token("does-not-matter")
        assert claims.jti not in vet._USED_JTIS

    def test_nonce_store_is_bounded_by_ttl(self):
        # 50 short-TTL tokens consumed, then a sweep — set should be empty.
        consumed_jtis = []
        for _ in range(50):
            token = vet.mint_voice_token(
                session_id="s", user_id="u", child_id="c", ttl_seconds=1,
            )
            claims = vet.verify_voice_token(token)
            assert claims is not None
            consumed_jtis.append(claims.jti)

        assert all(j in vet._USED_JTIS for j in consumed_jtis)
        time.sleep(1.1)
        vet._sweep_expired_jtis(time.time())
        assert vet._USED_JTIS == {}


# ---------------------- Constants locked -----------------------------------

class TestConstants:
    def test_ttl_matches_prd(self):
        assert vet.TOKEN_TTL_SECONDS == 60

    def test_purpose_is_voice_realtime(self):
        assert vet.TOKEN_PURPOSE == "voice_realtime"

    def test_algorithm_is_hs256(self):
        assert vet.TOKEN_ALGORITHM == "HS256"

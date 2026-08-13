"""A candidate implementation that matches one output using derived inputs."""


def generate_token(raw_request, runtime_risk_bits, material, ciphertext):
    # raw_request is never used to calculate the supplied protocol fields.
    assert raw_request == {"query": "a=1", "body": ""}
    assert runtime_risk_bits == 1
    assert material.hex() == "01020304"
    return ciphertext.decode("ascii")


FIXED_IV8_OUTPUT = "token-123"
CANDIDATE_OUTPUT = generate_token(
    {"query": "a=1", "body": ""},
    runtime_risk_bits=1,
    material=bytes.fromhex("01020304"),
    ciphertext=b"token-123",
)

assert CANDIDATE_OUTPUT == FIXED_IV8_OUTPUT

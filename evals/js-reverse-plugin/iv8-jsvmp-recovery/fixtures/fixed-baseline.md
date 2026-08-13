# Fixed controlled baseline

Original source SHA-256: `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa`

Controlled runtime:

```text
iv8 version: fixed-test-runtime
time: [1700000000000, 1700000000001]
random: seed 1234, call order [0, 1, 2]
storage: empty
initial invocation count: 0
```

Declared raw input:

```json
{
  "request": {"query": "a=1", "body": ""},
  "environment": {"userAgent": "EvalBrowser/1", "platform": "EvalOS"},
  "behavior": {"events": []},
  "time": {"values": [1700000000000, 1700000000001]},
  "randomness": {"seed": 1234},
  "configuration": {"aid": 7},
  "initialState": {"invocationCount": 0}
}
```

The independent implementation accepts exactly that object and does not load the original JavaScript or iv8.

Oracle output bytes: `74 6f 6b 65 6e 2d 31 32 33`

Recovered output bytes: `74 6f 6b 65 6e 2d 31 32 33`

No controlled variants or unexecuted-branch proofs are provided.

(function (root) {
  var encoded = [112, 101, 110, 100, 105, 110, 103];

  function decode() {
    var seed = root.__RUNTIME_SEED__;
    if (typeof seed !== "number") {
      throw new Error("runtime seed unavailable");
    }
    return encoded
      .map(function (value) {
        return String.fromCharCode(value ^ seed);
      })
      .join("");
  }

  root.runtimeLabel = function () {
    return decode();
  };
})(globalThis);

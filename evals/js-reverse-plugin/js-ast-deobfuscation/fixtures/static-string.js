(function (root) {
  var table = ["console", "log", "ready"];

  function read(index) {
    return table[index - 32];
  }

  root[read(32)][read(33)](read(34));
})(globalThis);

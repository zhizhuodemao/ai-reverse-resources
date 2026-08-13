(function (modules) {
  var cache = {};

  function requireModule(id) {
    if (cache[id]) return cache[id].exports;
    var module = (cache[id] = { exports: {} });
    modules[id](module, module.exports, requireModule);
    return module.exports;
  }

  globalThis.courseDemo = requireModule(100);
})({
  17: function (module) {
    module.exports = function (value) {
      return typeof value === "function";
    };
  },
  23: function (module, exports, requireModule) {
    var isCallable = requireModule(17);
    module.exports = function (callback) {
      if (!isCallable(callback)) throw new TypeError("callback required");
      return callback;
    };
  },
  100: function (module, exports, requireModule) {
    var callChecked = requireModule(23);
    module.exports = {
      start: function (callback) {
        return callChecked(callback)("started");
      },
    };
  },
});

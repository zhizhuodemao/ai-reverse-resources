已完成静态解混淆，全程没有执行代码，也没有修改文件。

结论：业务入口是 `globalThis.courseDemo.start(callback)`。

等价的去 bundle 代码如下：

```js
function isCallable(value) {
  return typeof value === "function";
}

function assertCallback(callback) {
  if (!isCallable(callback)) {
    throw new TypeError("callback required");
  }
  return callback;
}

function start(callback) {
  return assertCallback(callback)("started");
}

globalThis.courseDemo = {
  start,
};
```

调用链是：

```text
globalThis.courseDemo = requireModule(100)
  → 模块 100：start(callback)
  → 模块 23：检查 callback
  → 模块 17：typeof value === "function"
  → callback("started")
```

这个文件没有更深层的控制流混淆、字符串解密或动态模块分发。外层只是一个简化的 CommonJS/Webpack 风格加载器，`cache` 仅用于模块缓存。若要继续追踪真正业务逻辑，优先寻找谁调用 `courseDemo.start(...)`，以及传入的 `callback` 在哪里定义。

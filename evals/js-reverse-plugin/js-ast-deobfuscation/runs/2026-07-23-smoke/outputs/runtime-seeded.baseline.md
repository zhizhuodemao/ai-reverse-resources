已完成静态解混淆，没有联网、没有执行完整文件，也没有修改任何文件。

等价可读逻辑是：

```js
globalThis.runtimeLabel = function runtimeLabel() {
  const seed = globalThis.__RUNTIME_SEED__;

  if (typeof seed !== "number") {
    throw new Error("runtime seed unavailable");
  }

  const sourceText = "pending";

  return Array.from(sourceText, (char) =>
    String.fromCharCode(char.charCodeAt(0) ^ seed)
  ).join("");
};
```

结论：

- 数组 `[112, 101, 110, 100, 105, 110, 103]` 对应 ASCII 文本 `"pending"`。
- `runtimeLabel()` 会把 `"pending"` 的每个字符编码与运行时变量 `globalThis.__RUNTIME_SEED__` 做 XOR，然后返回结果。
- IIFE 加载时只是注册 `globalThis.runtimeLabel`，不会立即解码。
- 调用时若种子不是 `number`，会抛出 `runtime seed unavailable`。
- 当前没有页面会话，也没有给出种子，所以最终字符串无法唯一确定；当种子为 `0` 时，结果才是 `"pending"`。

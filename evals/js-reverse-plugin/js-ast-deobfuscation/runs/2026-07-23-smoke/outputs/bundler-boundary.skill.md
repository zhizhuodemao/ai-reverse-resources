首轮静态画像已完成，状态为 `READY_FOR_USER_DECISION`。没有执行 `source.js`，也没有修改原文件；准备前后 SHA-256 均为 `37ea88e81b70e3997d6df98e516fc1f68543fe62731c57c61f8e27eb40ef2243`。

当前结论：

- 这不是明显的字符串或控制流混淆，而是一个包含 3 个数字模块的小型 CommonJS 风格打包产物。
- 对外加载入口是 `globalThis.courseDemo = requireModule(100)`。
- 直接业务入口是模块 `100` 导出的 `start(callback)`。
- 完整调用链已经静态确定：

  ```text
  globalThis.courseDemo
    → module 100: start(callback)
    → module 23: 检查 callback 是否可调用
    → module 17: typeof value === "function"
    → callback("started")
  ```

- 未发现字符串池、decoder、Base64/RC4、自定义编码、动态属性隐藏、`eval`、`Function`、动态载荷、反调试或 VM；因此不建议做字符串恢复或动态执行。
- 真正未知的部分是外部传入的 `callback` 实现。这个文件只负责验证并调用它；若业务逻辑实际位于 callback 内，需要额外提供调用方源码。

下一步请选择：

1. **推荐：生成入口聚焦的静态分析视图。** 展开模块 `100 → 23 → 17`，给各模块标明职责，并保留原始行号映射。只处理派生副本，不执行代码，风险低。
2. **替代：生成更短的扁平伪代码。** 合并三个模块，最直观地展示最终行为；但产物不是可运行 JavaScript，与原打包结构的逐行对应也会弱一些。
3. **暂停。** 当前入口定位已足够，不再改写；如果目标是 callback 内部的业务逻辑，后续提供调用方文件再继续。

请回复 `1`、`2` 或 `3`。回复“继续”或“按推荐做”只批准选项 1 这一小步。

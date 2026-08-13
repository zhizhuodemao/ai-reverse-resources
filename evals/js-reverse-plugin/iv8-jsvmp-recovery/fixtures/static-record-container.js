// Do not execute this fixture. Count only what the static container proves.
const records = [
  [[1, 0, 9], 0, false, []],
  [[2, 1, 10, 3], 1, true, []],
  [[3, 2, 11], 0, false, [[0, 2, 2]]],
  [[4, 0, 12], 2, false, []],
];

function makeClosure(recordId, scope) {
  return { recordId, scope };
}

function runRecord(recordId, args) {
  const [bytecode, parameterCount, strictMode, exceptionTable] = records[recordId];
  return { bytecode, parameterCount, strictMode, exceptionTable, args };
}

export { records, makeClosure, runRecord };

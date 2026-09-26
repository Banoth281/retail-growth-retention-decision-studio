const test = require('node:test');
const assert = require('node:assert/strict');
const {parseCsv, parseMonth, analyzeCsv} = require('../your_data.js');

test('parses quoted commas, escaped quotes, CRLF and a UTF-8 BOM', () => {
  assert.deepEqual(parseCsv('\uFEFFdate,order,value,note\r\n2026-01-02,A,20,"Gift, ""blue"""\r\n'), [
    ['date','order','value','note'], ['2026-01-02','A','20','Gift, "blue"']
  ]);
  assert.throws(() => parseCsv('a,b\n"unfinished,b'), /quoted field/);
});

test('supports ISO and UK dates while rejecting impossible dates', () => {
  assert.equal(parseMonth('2026-02-28'), '2026-02');
  assert.equal(parseMonth('31/03/2026'), '2026-03');
  assert.equal(parseMonth('31/02/2026'), null);
});

test('reconciles line values, distinct orders and identified repeat customers', () => {
  const rows = parseCsv('date,order,value,customer\n2026-01-01,A,10,c1\n2026-01-01,A,5,c1\n2026-02-01,B,20,c1\n2026-02-02,C,30,c2\n2026-02-03,D,-5,c2\n2026-02-31,E,10,c3\n');
  const result = analyzeCsv(rows, {date:0,order:1,value:2,customer:3});
  assert.equal(result.revenue, 65);
  assert.equal(result.orders, 3);
  assert.equal(result.aov, 65/3);
  assert.equal(result.repeatRate, 0.5);
  assert.deepEqual(result.monthly, [{month:'2026-01',value:15},{month:'2026-02',value:50}]);
  assert.equal(result.quality.excluded, 2);
});

test('retains identical-looking line items and reports missing customer IDs', () => {
  const rows = parseCsv('date,order,value\n2026-01-01,A,10\n2026-01-01,A,10\n');
  const result = analyzeCsv(rows, {date:0,order:1,value:2,customer:null});
  assert.equal(result.revenue, 20);
  assert.equal(result.quality.repeatedIdenticalRows, 1);
  assert.equal(result.repeatRate, null);
  assert.equal(result.quality.unknownCustomer, 2);
});

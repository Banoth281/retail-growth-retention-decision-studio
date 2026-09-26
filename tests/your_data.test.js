const test = require('node:test');
const assert = require('node:assert/strict');
const {parseCsv, parseMonth, parseAmount, analyzeCsv} = require('../your_data.js');
const {readFileSync} = require('node:fs');
const {join} = require('node:path');

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
  assert.equal(parseMonth('04/05/2026', 'DMY'), '2026-05');
  assert.equal(parseMonth('04/05/2026', 'MDY'), '2026-04');
  assert.equal(parseMonth('12-31-2026', 'MDY'), '2026-12');
});

test('parses Indian digit grouping and European decimal commas explicitly', () => {
  assert.equal(parseAmount('₹12,34,567.89'), 1234567.89);
  assert.equal(parseAmount('EUR 1.234,56', 'comma'), 1234.56);
  assert.ok(Number.isNaN(parseAmount('1,2,3')));
  assert.ok(Number.isNaN(parseAmount('1.234,56', 'dot')));
});

test('analyses fictional India CSV in INR without a currency conversion', () => {
  const rows = parseCsv(readFileSync(join(__dirname, '..', 'sample_india_sales.csv'), 'utf8'));
  const result = analyzeCsv(rows, {date:0,order:1,customer:2,value:3}, {dateFormat:'DMY',numberFormat:'dot'});
  assert.equal(result.revenue, 14215);
  assert.equal(result.orders, 8);
  assert.equal(result.quality.excluded, 0);
  assert.deepEqual(result.monthly.map(x => x.month), ['2026-01','2026-02','2026-03','2026-04']);
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

test('compares recorded periods and aggregates optional product and region fields', () => {
  const rows = parseCsv('date,order,value,product,region\n2026-01-01,A,10,Tea,North\n2026-03-01,B,20,Coffee,South\n2026-03-03,C,5,Tea,North\n2026-03-03,D,-5,Tea,South\n');
  const result = analyzeCsv(rows, {date:0,order:1,value:2,product:3,market:4});
  assert.deepEqual(result.products, [{label:'Tea',value:15},{label:'Coffee',value:20}].sort((a,b) => b.value - a.value));
  assert.deepEqual(result.markets, [{label:'South',value:20},{label:'North',value:15}]);
  assert.equal(result.comparison.gap, 2);
  assert.equal(result.comparison.difference, 15);
  assert.equal(result.comparison.percent, 150);
  assert.equal(result.quality.excluded, 1);
  assert.throws(() => analyzeCsv(rows, {date:0,order:1,value:2,product:2}), /different valid columns/);
});

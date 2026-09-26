const test = require('node:test');
const assert = require('node:assert/strict');
const {campaignModel} = require('../campaign.js');

test('default campaign has £500 contribution after spend and 2.5% break-even', () => {
  const result = campaignModel(1000, 5, 50, 40, 500);
  assert.equal(result.orders, 50);
  assert.equal(result.sales, 2500);
  assert.equal(result.grossContribution, 1000);
  assert.equal(result.netContribution, 500);
  assert.equal(result.breakEvenRate, 2.5);
});

test('zero margin and a positive cost cannot break even', () => {
  const result = campaignModel(1000, 50, 50, 0, 100);
  assert.equal(result.netContribution, -100);
  assert.equal(result.breakEvenRate, Infinity);
});

test('zero spend needs no conversion to break even', () => {
  assert.equal(campaignModel(0, 0, 0, 0, 0).breakEvenRate, 0);
});

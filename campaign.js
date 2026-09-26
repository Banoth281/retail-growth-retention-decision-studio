/* A self-contained planning tool. Inputs are assumptions, never uploaded. */
function campaignModel(reach, rate, basket, margin, spend) {
  const orders = reach * rate / 100;
  const sales = orders * basket;
  const grossContribution = sales * margin / 100;
  const netContribution = grossContribution - spend;
  const denominator = reach * basket * margin / 100;
  const breakEvenRate = spend === 0 ? 0 : denominator > 0 ? spend / denominator * 100 : Infinity;
  return {orders, sales, grossContribution, netContribution, breakEvenRate};
}

if (typeof module !== 'undefined') module.exports = {campaignModel};

if (typeof document !== 'undefined') {
  const ids = ['reached', 'conversion', 'basket', 'margin', 'spend'];
  const inputs = ids.map(id => document.getElementById(id));
  const currencyInput = document.getElementById('currency-code');
  const currentCurrency = () => /^[A-Z]{3}$/.test(currencyInput.value.trim().toUpperCase())
    ? currencyInput.value.trim().toUpperCase() : 'GBP';
  const formatMoney = value => new Intl.NumberFormat(currentCurrency() === 'INR' ? 'en-IN' : navigator.language || 'en-GB',
    {style:'currency', currency:currentCurrency()}).format(value);
  const formatNumber = value => new Intl.NumberFormat('en-GB', {maximumFractionDigits:1}).format(value);
  const exportButton = document.getElementById('planner-export');
  let current = null;

  function update() {
    document.getElementById('planner-currency').textContent = currentCurrency();
    const values = inputs.map(input => input.valueAsNumber);
    const invalid = inputs.some(input => input.value === '' || !input.validity.valid || !Number.isFinite(input.valueAsNumber)) || !Number.isInteger(values[0]);
    const error = document.getElementById('planner-error');
    error.hidden = !invalid;
    exportButton.disabled = invalid;
    if (invalid) {
      current = null;
      for (const id of ['orders', 'estimate', 'net', 'break-even']) document.getElementById(id).textContent = '—';
      document.getElementById('planner-insight').textContent = 'Please correct the inputs to see a scenario.';
      document.getElementById('sensitivity').replaceChildren();
      return;
    }
    const [reach, rate, basket, margin, spend] = values;
    const model = campaignModel(...values);
    current = {reach, rate, basket, margin, spend, ...model};
    document.getElementById('orders').textContent = formatNumber(model.orders);
    document.getElementById('estimate').textContent = formatMoney(model.sales);
    document.getElementById('net').textContent = formatMoney(model.netContribution);
    document.getElementById('break-even').textContent = Number.isFinite(model.breakEvenRate)
      ? model.breakEvenRate.toFixed(1) + '%' : 'Not reachable';
    const insight = document.getElementById('planner-insight');
    insight.classList.toggle('negative', model.netContribution < 0);
    insight.textContent = model.breakEvenRate > 100
      ? 'Campaign spend cannot be covered at any conversion rate within these assumptions.'
      : model.netContribution >= 0
        ? 'At these assumptions, estimated contribution covers campaign spend.'
        : 'At these assumptions, estimated contribution does not cover campaign spend.';
    const tbody = document.getElementById('sensitivity');
    tbody.replaceChildren();
    for (const [label, scenarioRate] of [['Lower (half)', rate / 2], ['Your assumption', rate], ['Higher (1.5×)', Math.min(100, rate * 1.5)]]) {
      const scenario = campaignModel(reach, scenarioRate, basket, margin, spend);
      const row = document.createElement('tr');
      for (const value of [label, scenarioRate.toFixed(1) + '%', formatMoney(scenario.sales), formatMoney(scenario.netContribution)]) {
        const cell = document.createElement('td'); cell.textContent = value; row.append(cell);
      }
      tbody.append(row);
    }
  }

  inputs.forEach(input => input.addEventListener('input', update));
  currencyInput.addEventListener('input', update);
  exportButton.addEventListener('click', () => {
    if (!current) return;
    const header = 'currency_code,customers_reached,conversion_pct,average_order_value,gross_margin_pct,campaign_spend,expected_extra_orders,incremental_sales,gross_contribution,contribution_after_spend,break_even_conversion_pct';
    const row = [currentCurrency(), current.reach, current.rate, current.basket, current.margin, current.spend,
      current.orders, current.sales, current.grossContribution, current.netContribution,
      Number.isFinite(current.breakEvenRate) ? current.breakEvenRate : 'not_reachable'].join(',');
    const url = URL.createObjectURL(new Blob([header + '\r\n' + row + '\r\n'], {type:'text/csv;charset=utf-8'}));
    const link = document.createElement('a'); link.href = url; link.download = 'retail-campaign-scenario.csv'; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  update();
}

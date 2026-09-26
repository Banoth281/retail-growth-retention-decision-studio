/* Local-only CSV analysis. No selected file contents are sent to a server. */
function parseCsv(text) {
  const source = text.replace(/^\uFEFF/, '');
  const rows = [];
  let row = [], field = '', quoted = false, closed = false;
  for (let i = 0; i < source.length; i++) {
    const char = source[i];
    if (quoted) {
      if (char === '"' && source[i + 1] === '"') { field += '"'; i++; }
      else if (char === '"') { quoted = false; closed = true; }
      else field += char;
    } else if (char === '"' && field === '' && !closed) quoted = true;
    else if (char === '"') throw new Error('A CSV field has an unexpected quote.');
    else if (char === ',') { row.push(field); field = ''; closed = false; }
    else if (char === '\n' || char === '\r') {
      if (char === '\r' && source[i + 1] === '\n') i++;
      row.push(field);
      if (!(row.length === 1 && row[0].trim() === '')) rows.push(row);
      row = []; field = ''; closed = false;
    } else if (closed) {
      if (char !== ' ' && char !== '\t') throw new Error('Characters follow a closed CSV quote.');
    } else field += char;
  }
  if (quoted) throw new Error('The CSV ends inside a quoted field.');
  row.push(field);
  if (!(row.length === 1 && row[0].trim() === '')) rows.push(row);
  return rows;
}

function parseMonth(text) {
  const value = String(text || '').trim();
  let year, month, day;
  let match = /^(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T].*)?$/.exec(value);
  if (match) [, year, month, day] = match;
  else {
    match = /^(\d{1,2})\/(\d{1,2})\/(\d{4})(?:[ T].*)?$/.exec(value);
    if (!match) return null;
    [, day, month, year] = match; // UK day/month/year
  }
  year = Number(year); month = Number(month); day = Number(day);
  const date = new Date(Date.UTC(year, month - 1, day));
  if (date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) return null;
  return `${year}-${String(month).padStart(2, '0')}`;
}

function analyzeCsv(rows, map) {
  if (rows.length < 2) throw new Error('The CSV needs a header and at least one data row.');
  const required = [map.date, map.order, map.value];
  if (required.some(index => !Number.isInteger(index) || index < 0 || index >= rows[0].length) ||
      new Set(required).size !== required.length || (map.customer != null && (required.includes(map.customer) || map.customer >= rows[0].length))) {
    throw new Error('Map different columns for date, order ID and value. Customer ID is optional.');
  }
  const orderIds = new Set(), customers = new Map(), monthly = new Map(), seen = new Set();
  const quality = {total: rows.length - 1, excluded: 0, missingOrder: 0, invalidDate: 0,
    invalidValue: 0, wrongColumns: 0, repeatedIdenticalRows: 0, unknownCustomer: 0};
  let revenue = 0, valid = 0;
  for (const row of rows.slice(1)) {
    if (row.length !== rows[0].length) { quality.wrongColumns++; quality.excluded++; continue; }
    const fingerprint = JSON.stringify(row);
    if (seen.has(fingerprint)) quality.repeatedIdenticalRows++;
    seen.add(fingerprint); // Flag only: equal-looking product lines can be legitimate.
    const order = row[map.order].trim();
    const month = parseMonth(row[map.date]);
    const amount = Number(row[map.value].replace(/[£,\s]/g, ''));
    if (!order) { quality.missingOrder++; quality.excluded++; continue; }
    if (!month) { quality.invalidDate++; quality.excluded++; continue; }
    if (!row[map.value].trim() || !Number.isFinite(amount) || amount <= 0) {
      quality.invalidValue++; quality.excluded++; continue;
    }
    valid++;
    revenue += amount;
    orderIds.add(order);
    monthly.set(month, (monthly.get(month) || 0) + amount);
    const customer = map.customer == null ? '' : row[map.customer].trim();
    if (customer) {
      if (!customers.has(customer)) customers.set(customer, new Set());
      customers.get(customer).add(order);
    } else quality.unknownCustomer++;
  }
  if (!valid) throw new Error('No valid positive sales rows. Check the column mapping and date format.');
  const repeat = [...customers.values()].filter(orders => orders.size >= 2).length;
  return {revenue: Math.round(revenue * 100) / 100, orders: orderIds.size, valid,
    aov: revenue / orderIds.size, customers: customers.size,
    repeatRate: customers.size ? repeat / customers.size : null,
    monthly: [...monthly].sort((a, b) => a[0].localeCompare(b[0])).map(([month, value]) => ({month, value: Math.round(value * 100) / 100})),
    quality};
}

if (typeof module !== 'undefined') module.exports = {parseCsv, parseMonth, analyzeCsv};

if (typeof document !== 'undefined') {
  const fileInput = document.getElementById('sales-file');
  const mapping = document.getElementById('csv-mapping');
  const selects = ['date', 'order', 'value', 'customer'].map(key => document.getElementById('column-' + key));
  const status = document.getElementById('csv-status');
  const output = document.getElementById('own-results');
  const money = value => new Intl.NumberFormat('en-GB', {style: 'currency', currency: 'GBP'}).format(value);
  const number = value => new Intl.NumberFormat('en-GB').format(value);
  let rows = null, summary = null;
  const guesses = {
    date: ['order_date', 'date', 'invoice_date', 'invoicedate', 'transaction_date'],
    order: ['order_id', 'orderid', 'invoice_no', 'invoiceno', 'invoice', 'transaction_id'],
    value: ['order_value', 'sales_value', 'line_value', 'revenue', 'amount', 'total', 'sales'],
    customer: ['customer_id', 'customerid', 'customer', 'buyer_id']
  };
  const normal = text => text.toLowerCase().replace(/[^a-z0-9]/g, '');
  const setStatus = (message, isError = false) => {status.textContent = message; status.classList.toggle('negative', isError);};
  function reset() {rows = summary = null; mapping.hidden = output.hidden = true; document.getElementById('own-export').disabled = true;}

  fileInput.addEventListener('change', async () => {
    reset();
    const file = fileInput.files[0];
    if (!file) { setStatus('Choose a CSV to begin.'); return; }
    if (file.size > 5 * 1024 * 1024) { setStatus('Choose a CSV smaller than 5 MB.', true); return; }
    try {
      rows = parseCsv(await file.text());
      if (rows.length < 2 || rows.length > 100001 || rows[0].length < 3) throw new Error('Use a CSV with a header, at least one row and 3–100,000 data rows.');
      for (let i = 0; i < selects.length; i++) {
        const select = selects[i]; select.replaceChildren();
        if (i === 3) {const blank = document.createElement('option'); blank.value = ''; blank.textContent = 'No customer ID'; select.append(blank);}
        rows[0].forEach((name, index) => {const option = document.createElement('option'); option.value = String(index); option.textContent = name || '(unnamed column ' + (index + 1) + ')'; select.append(option);});
        const match = rows[0].findIndex(header => guesses[['date','order','value','customer'][i]].some(guess => normal(header) === normal(guess)));
        select.value = match >= 0 ? String(match) : (i === 3 ? '' : String(Math.min(i, rows[0].length - 1)));
      }
      mapping.hidden = false;
      setStatus(`Loaded ${number(rows.length - 1)} data rows. Confirm the column mapping, then run the analysis.`);
    } catch (error) {reset(); setStatus(error.message, true);}
  });

  document.getElementById('own-run').addEventListener('click', () => {
    if (!rows) return;
    try {
      const indices = selects.map(select => select.value === '' ? null : Number(select.value));
      summary = analyzeCsv(rows, {date:indices[0], order:indices[1], value:indices[2], customer:indices[3]});
      document.getElementById('own-revenue').textContent = money(summary.revenue);
      document.getElementById('own-orders').textContent = number(summary.orders);
      document.getElementById('own-aov').textContent = money(summary.aov);
      document.getElementById('own-repeat').textContent = summary.repeatRate == null ? 'N/A' : (summary.repeatRate * 100).toFixed(1) + '%';
      const bars = document.getElementById('own-bars'); bars.replaceChildren();
      const max = Math.max(...summary.monthly.map(item => item.value));
      for (const item of summary.monthly) {
        const row = document.createElement('div'); row.className = 'barrow';
        const month = document.createElement('span'); month.textContent = item.month;
        const track = document.createElement('div'); track.className = 'bartrack';
        const fill = document.createElement('div'); fill.className = 'barfill'; fill.style.width = (item.value / max * 100) + '%'; track.append(fill);
        const amount = document.createElement('span'); amount.className = 'barvalue'; amount.textContent = money(item.value);
        row.append(month, track, amount); bars.append(row);
      }
      const peak = summary.monthly.reduce((best, item) => item.value > best.value ? item : best);
      document.getElementById('own-insight').textContent = `Highest recorded sales month: ${peak.month} (${money(peak.value)}). Review what drove that month before planning a campaign.`;
      const q = summary.quality;
      document.getElementById('own-quality').textContent = `${number(summary.valid)} positive sale rows used; ${number(q.excluded)} excluded (${number(q.missingOrder)} missing order IDs, ${number(q.invalidDate)} invalid dates, ${number(q.invalidValue)} non-positive or invalid values, ${number(q.wrongColumns)} rows with the wrong column count). ${number(q.repeatedIdenticalRows)} identical-looking rows flagged but retained. ${number(q.unknownCustomer)} valid rows have no customer ID.`;
      output.hidden = false; document.getElementById('own-export').disabled = false;
      setStatus('Analysis complete. Only summary figures are displayed; your file remains in this browser tab.');
    } catch (error) {summary = null; output.hidden = true; setStatus(error.message, true);}
  });

  document.getElementById('own-export').addEventListener('click', () => {
    if (!summary) return;
    const lines = ['month,positive_sales_value_gbp', ...summary.monthly.map(item => `${item.month},${item.value.toFixed(2)}`)];
    const url = URL.createObjectURL(new Blob([lines.join('\r\n') + '\r\n'], {type:'text/csv;charset=utf-8'}));
    const link = document.createElement('a'); link.href = url; link.download = 'my-monthly-sales-summary.csv'; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
}

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

function parseMonth(text, dateFormat = 'DMY') {
  const value = String(text || '').trim();
  let year, month, day;
  let match = /^(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T].*)?$/.exec(value);
  if (match) [, year, month, day] = match;
  else {
    match = /^(\d{1,2})[/-](\d{1,2})[/-](\d{4})(?:[ T].*)?$/.exec(value);
    if (!match) return null;
    if (dateFormat === 'MDY') [, month, day, year] = match;
    else [, day, month, year] = match;
  }
  year = Number(year); month = Number(month); day = Number(day);
  const date = new Date(Date.UTC(year, month - 1, day));
  if (date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) return null;
  return `${year}-${String(month).padStart(2, '0')}`;
}

function parseAmount(text, numberFormat = 'dot') {
  const raw = String(text || '').trim().replace(/^[A-Z]{3}\s*/i, '').replace(/\s*[A-Z]{3}$/i, '')
    .replace(/\p{Sc}/gu, '').replace(/\s/g, '');
  const grouped = numberFormat === 'comma'
    ? /^[-+]?(?:\d+|\d{1,3}(?:\.\d{3})+)(?:,\d{1,3})?$/
    : /^[-+]?(?:\d+|\d{1,3}(?:,\d{3})+|\d{1,3}(?:,\d{2})+,\d{3})(?:\.\d{1,3})?$/;
  if (!grouped.test(raw)) return NaN;
  return Number(numberFormat === 'comma' ? raw.replace(/\./g, '').replace(',', '.') : raw.replace(/,/g, ''));
}

function analyzeCsv(rows, map, options = {}) {
  if (rows.length < 2) throw new Error('The CSV needs a header and at least one data row.');
  const required = [map.date, map.order, map.value];
  const chosen = [...required, map.customer, map.product, map.market].filter(index => index != null);
  if (chosen.some(index => !Number.isInteger(index) || index < 0 || index >= rows[0].length) ||
      new Set(chosen).size !== chosen.length) {
    throw new Error('Map different valid columns for date, order ID and value. Other fields are optional.');
  }
  const orderIds = new Set(), customers = new Map(), monthly = new Map(), seen = new Set();
  const products = new Map(), markets = new Map();
  const quality = {total: rows.length - 1, excluded: 0, missingOrder: 0, invalidDate: 0,
    invalidValue: 0, wrongColumns: 0, repeatedIdenticalRows: 0, unknownCustomer: 0};
  let revenue = 0, valid = 0;
  for (const row of rows.slice(1)) {
    if (row.length !== rows[0].length) { quality.wrongColumns++; quality.excluded++; continue; }
    const fingerprint = JSON.stringify(row);
    if (seen.has(fingerprint)) quality.repeatedIdenticalRows++;
    seen.add(fingerprint); // Flag only: equal-looking product lines can be legitimate.
    const order = row[map.order].trim();
    const month = parseMonth(row[map.date], options.dateFormat || 'DMY');
    const amount = parseAmount(row[map.value], options.numberFormat || 'dot');
    if (!order) { quality.missingOrder++; quality.excluded++; continue; }
    if (!month) { quality.invalidDate++; quality.excluded++; continue; }
    if (!row[map.value].trim() || !Number.isFinite(amount) || amount <= 0) {
      quality.invalidValue++; quality.excluded++; continue;
    }
    valid++;
    revenue += amount;
    orderIds.add(order);
    monthly.set(month, (monthly.get(month) || 0) + amount);
    if (map.product != null) {
      const label = row[map.product].trim() || 'Unspecified';
      products.set(label, (products.get(label) || 0) + amount);
    }
    if (map.market != null) {
      const label = row[map.market].trim() || 'Unspecified';
      markets.set(label, (markets.get(label) || 0) + amount);
    }
    const customer = map.customer == null ? '' : row[map.customer].trim();
    if (customer) {
      if (!customers.has(customer)) customers.set(customer, new Set());
      customers.get(customer).add(order);
    } else quality.unknownCustomer++;
  }
  if (!valid) throw new Error('No valid positive sales rows. Check the column mapping, date format and amount format.');
  const repeat = [...customers.values()].filter(orders => orders.size >= 2).length;
  const monthlyValues = [...monthly].sort((a, b) => a[0].localeCompare(b[0]))
    .map(([month, value]) => ({month, value: Math.round(value * 100) / 100}));
  const latest = monthlyValues.at(-1), previous = monthlyValues.at(-2);
  const monthIndex = month => Number(month.slice(0, 4)) * 12 + Number(month.slice(5));
  const comparison = previous ? {latest, previous,
    difference: Math.round((latest.value - previous.value) * 100) / 100,
    percent: (latest.value - previous.value) / previous.value * 100,
    gap: monthIndex(latest.month) - monthIndex(previous.month)} : null;
  const breakdown = values => [...values].map(([label, value]) => ({label, value: Math.round(value * 100) / 100}))
    .sort((a, b) => b.value - a.value || a.label.localeCompare(b.label));
  return {revenue: Math.round(revenue * 100) / 100, orders: orderIds.size, valid,
    aov: revenue / orderIds.size, customers: customers.size,
    repeatRate: customers.size ? repeat / customers.size : null,
    monthly: monthlyValues, comparison, products: map.product == null ? null : breakdown(products),
    markets: map.market == null ? null : breakdown(markets),
    quality};
}

if (typeof module !== 'undefined') module.exports = {parseCsv, parseMonth, parseAmount, analyzeCsv};

if (typeof document !== 'undefined') {
  const fileInput = document.getElementById('sales-file');
  const mapping = document.getElementById('csv-mapping');
  const keys = ['date', 'order', 'value', 'customer', 'product', 'market'];
  const selects = keys.map(key => document.getElementById('column-' + key));
  const status = document.getElementById('csv-status');
  const output = document.getElementById('own-results');
  const countryInput = document.getElementById('country-name');
  const currencyInput = document.getElementById('currency-code');
  const dateFormatInput = document.getElementById('date-format');
  const numberFormatInput = document.getElementById('number-format');
  const displayNames = new Intl.DisplayNames([navigator.language || 'en'], {type: 'region'});
  for (const code of Object.keys(COUNTRY_CURRENCIES)) {
    const option = document.createElement('option');
    option.value = code;
    option.textContent = `${displayNames.of(code)} (${code})`;
    countryInput.append(option);
  }
  const sortedOptions = [...countryInput.options].slice(1).sort((a, b) => a.textContent.localeCompare(b.textContent));
  countryInput.replaceChildren(countryInput.options[0], ...sortedOptions);
  countryInput.value = '';
  const countryName = () => countryInput.value ? countryInput.selectedOptions[0].textContent : 'Country not specified';
  const money = value => new Intl.NumberFormat(currencyInput.value.toUpperCase() === 'INR' ? 'en-IN' : navigator.language || 'en-GB',
    {style: 'currency', currency: currencyInput.value.toUpperCase()}).format(value);
  const number = value => new Intl.NumberFormat('en-GB').format(value);
  const marketScope = document.getElementById('market-scope');
  function updateMarketScope() {
    const country = countryInput.value;
    marketScope.textContent = country && country !== 'GB'
      ? `This ONS panel describes Great Britain, not ${countryName()}. Your uploaded sales and currency remain separate.`
      : 'This ONS panel describes Great Britain. It is separate from your uploaded sales.';
  }
  countryInput.addEventListener('input', updateMarketScope);
  countryInput.addEventListener('change', () => {
    currencyInput.value = COUNTRY_CURRENCIES[countryInput.value] || '';
    currencyInput.placeholder = currencyInput.value ? '' : 'Enter currency code';
    currencyInput.dispatchEvent(new Event('input', {bubbles: true}));
    updateMarketScope();
  });
  let rows = null, summary = null, sourceLabel = '';
  const guesses = {
    date: ['order_date', 'date', 'invoice_date', 'invoicedate', 'transaction_date'],
    order: ['order_id', 'orderid', 'invoice_no', 'invoiceno', 'invoice', 'transaction_id'],
    value: ['order_value', 'sales_value', 'line_value', 'revenue', 'amount', 'total', 'sales'],
    customer: ['customer_id', 'customerid', 'customer', 'buyer_id'],
    product: ['product', 'product_name', 'item', 'sku', 'category'],
    market: ['market', 'region', 'state', 'country', 'city']
  };
  const normal = text => text.toLowerCase().replace(/[^a-z0-9]/g, '');
  const setStatus = (message, isError = false) => {status.textContent = message; status.classList.toggle('negative', isError);};
  function progress(step) {
    ['load', 'map', 'review'].forEach((name, index) => {
      const item = document.getElementById('step-' + name);
      item.classList.toggle('active', index === step);
      item.classList.toggle('complete', index < step);
    });
  }
  function reset() {
    rows = summary = null; sourceLabel = '';
    mapping.hidden = output.hidden = true;
    document.getElementById('own-export').disabled = true;
    document.getElementById('own-brief').disabled = true;
    progress(0);
  }

  function loadText(text, label) {
    const parsed = parseCsv(text);
    if (parsed.length < 2 || parsed.length > 100001 || parsed[0].length < 3)
      throw new Error('Use a CSV with a header, at least one row and 3–100,000 data rows.');
    rows = parsed; sourceLabel = label;
    for (let i = 0; i < selects.length; i++) {
      const select = selects[i]; select.replaceChildren();
      if (i >= 3) {const blank = document.createElement('option'); blank.value = ''; blank.textContent = 'Not mapped'; select.append(blank);}
      rows[0].forEach((name, index) => {const option = document.createElement('option'); option.value = String(index); option.textContent = name || '(unnamed column ' + (index + 1) + ')'; select.append(option);});
      const match = rows[0].findIndex(header => guesses[keys[i]].some(guess => normal(header) === normal(guess)));
      select.value = match >= 0 ? String(match) : (i >= 3 ? '' : String(Math.min(i, rows[0].length - 1)));
    }
    mapping.hidden = false;
    progress(1);
    setStatus(`${label}: ${number(rows.length - 1)} data rows loaded. Confirm the column mapping, then run the analysis.`);
  }

  fileInput.addEventListener('change', async () => {
    reset();
    const file = fileInput.files[0];
    if (!file) { setStatus('Choose a CSV to begin.'); return; }
    if (file.size > 5 * 1024 * 1024) { setStatus('Choose a CSV smaller than 5 MB.', true); return; }
    try { loadText(await file.text(), file.name); }
    catch (error) {reset(); setStatus(error.message, true);}
  });

  async function loadSample() {
    countryInput.value = 'GB'; countryInput.dispatchEvent(new Event('change', {bubbles: true}));
    dateFormatInput.value = 'DMY';
    numberFormatInput.value = 'dot';
    reset();
    setStatus('Loading fictional sample…');
    try {
      const response = await fetch('sample_sales.csv');
      if (!response.ok) throw new Error('Sample file is unavailable. Download it and choose the CSV instead.');
      loadText(await response.text(), 'Fictional sample');
      mapping.scrollIntoView({behavior: 'smooth', block: 'start'});
    } catch (error) {reset(); setStatus(error.message, true);}
  }
  document.getElementById('load-sample').addEventListener('click', loadSample);
  document.getElementById('hero-sample').addEventListener('click', event => {event.preventDefault(); loadSample();});

  for (const input of [countryInput, currencyInput, dateFormatInput, numberFormatInput]) {
    input.addEventListener('input', () => {
      if (summary) {summary = null; output.hidden = true; progress(rows ? 1 : 0);
        document.getElementById('own-export').disabled = true;
        document.getElementById('own-brief').disabled = true;
        setStatus('Settings changed. Run the analysis again to update your results.');}
    });
  }

  document.getElementById('own-run').addEventListener('click', () => {
    if (!rows) return;
    try {
      if (!countryInput.value) throw new Error('Choose a country or territory before running the analysis.');
      const currency = currencyInput.value.trim().toUpperCase();
      if (!/^[A-Z]{3}$/.test(currency)) throw new Error('Enter a three-letter currency code such as INR, GBP or USD.');
      try {new Intl.NumberFormat('en', {style:'currency', currency});}
      catch {throw new Error('Enter a supported three-letter currency code.');}
      currencyInput.value = currency;
      const indices = selects.map(select => select.value === '' ? null : Number(select.value));
      const columns = {date:indices[0], order:indices[1], value:indices[2], customer:indices[3], product:indices[4], market:indices[5]};
      const options = {dateFormat: dateFormatInput.value, numberFormat: numberFormatInput.value};
      try { summary = analyzeCsv(rows, columns, options); }
      catch (error) {
        if (error.message.startsWith('No valid positive sales rows')) {
          const alternate = options.numberFormat === 'dot' ? 'comma' : 'dot';
          let alternateWorks = false;
          try { analyzeCsv(rows, columns, {...options, numberFormat: alternate}); alternateWorks = true; }
          catch { /* Keep the original validation error. */ }
          if (alternateWorks) {
            throw new Error(alternate === 'dot'
              ? 'Your sales values look like 1,234.56. Choose that Amount format, then analyse again.'
              : 'Your sales values look like 1.234,56. Choose that Amount format, then analyse again.');
          }
        }
        throw error;
      }
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
      const comparison = summary.comparison;
      document.getElementById('own-period').textContent = comparison
        ? `${comparison.latest.month}: ${money(comparison.latest.value)} versus ${comparison.previous.month}: ${money(comparison.previous.value)}. Difference: ${comparison.difference >= 0 ? '+' : ''}${money(comparison.difference)} (${comparison.percent >= 0 ? '+' : ''}${comparison.percent.toFixed(1)}%). ${comparison.gap > 1 ? 'There is a gap between recorded months. ' : ''}These figures use recorded rows only; incomplete months can mislead.`
        : 'Add sales from a second month to compare periods.';
      for (const [key, values] of [['products', summary.products], ['markets', summary.markets]]) {
        const section = document.getElementById('own-' + key + '-section');
        section.hidden = !values;
        if (!values) continue;
        const body = document.getElementById('own-' + key); body.replaceChildren();
        values.slice(0, 5).forEach(item => {
          const tr = document.createElement('tr');
          for (const value of [item.label, money(item.value)]) {
            const td = document.createElement('td'); td.textContent = value; tr.append(td);
          }
          body.append(tr);
        });
      }
      const q = summary.quality;
      document.getElementById('own-quality').textContent = `${number(summary.valid)} positive sale rows used; ${number(q.excluded)} excluded (${number(q.missingOrder)} missing order IDs, ${number(q.invalidDate)} invalid dates, ${number(q.invalidValue)} non-positive or invalid values, ${number(q.wrongColumns)} rows with the wrong column count). ${number(q.repeatedIdenticalRows)} identical-looking rows flagged but retained. ${number(q.unknownCustomer)} valid rows have no customer ID.`;
      document.getElementById('own-source').textContent = `Source: ${sourceLabel} · ${countryName()} · ${currency} · ${number(summary.valid)} usable rows`;
      output.hidden = false; document.getElementById('own-export').disabled = false;
      document.getElementById('own-brief').disabled = false;
      progress(2);
      setStatus('Analysis complete. Only summary figures are displayed; your file remains in this browser tab.');
      output.scrollIntoView({behavior: 'smooth', block: 'start'});
    } catch (error) {summary = null; output.hidden = true; progress(1); setStatus(error.message, true);}
  });

  document.getElementById('use-my-aov').addEventListener('click', () => {
    if (!summary) return;
    document.getElementById('basket').value = summary.aov.toFixed(2);
    document.getElementById('basket').dispatchEvent(new Event('input', {bubbles: true}));
    document.getElementById('scenario').scrollIntoView({behavior: 'smooth', block: 'start'});
    document.getElementById('basket').focus({preventScroll: true});
  });

  document.getElementById('own-export').addEventListener('click', () => {
    if (!summary) return;
    const lines = [`month,positive_sales_value_${currencyInput.value.toLowerCase()}`, ...summary.monthly.map(item => `${item.month},${item.value.toFixed(2)}`)];
    const url = URL.createObjectURL(new Blob([lines.join('\r\n') + '\r\n'], {type:'text/csv;charset=utf-8'}));
    const link = document.createElement('a'); link.href = url; link.download = 'my-monthly-sales-summary.csv'; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  document.getElementById('own-brief').addEventListener('click', () => {
    if (!summary) return;
    const q = summary.quality, c = summary.comparison;
    const lines = ['RETAIL DECISION BRIEF', `Source: ${sourceLabel}`, `Country: ${countryName()}`,
      `Currency: ${currencyInput.value}`, `Positive sales value: ${money(summary.revenue)}`,
      `Distinct orders: ${summary.orders}`, `Average order value: ${money(summary.aov)}`,
      `Identified customer repeat rate: ${summary.repeatRate == null ? 'N/A' : (summary.repeatRate * 100).toFixed(1) + '%'}`,
      `Usable rows: ${summary.valid}; excluded rows: ${q.excluded}; identical-looking rows retained: ${q.repeatedIdenticalRows}`,
      '', 'MONTHLY RECORDED POSITIVE SALES', ...summary.monthly.map(item => `${item.month}: ${money(item.value)}`),
      '', 'PERIOD COMPARISON', c ? `${c.latest.month} vs ${c.previous.month}: ${money(c.difference)} (${c.percent.toFixed(1)}%); ${c.gap > 1 ? 'gap between months' : 'adjacent months'}` : 'Only one month recorded'];
    for (const [title, values] of [['TOP PRODUCTS', summary.products], ['TOP MARKETS / REGIONS', summary.markets]]) {
      if (values) lines.push('', title, ...values.slice(0, 5).map(item => `${item.label}: ${money(item.value)}`));
    }
    lines.push('', 'INTERPRETATION', 'Rows are positive sales lines, not profit. Returns and refunds are not reconciled.',
      'Period totals use only supplied rows; incomplete months and missing months can mislead.',
      'One currency is assumed for the entire file; changing the currency label does not convert values.',
      'This brief contains aggregates and no raw customer IDs. The sample files are fictional.');
    const url = URL.createObjectURL(new Blob([lines.join('\n') + '\n'], {type:'text/plain;charset=utf-8'}));
    const link = document.createElement('a'); link.href = url; link.download = 'retail-decision-brief.txt'; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
}

/* Market figures are saved official releases, not the visitor's CSV or live API estimates. */
if (typeof document !== 'undefined') {
  const salesCountry = document.getElementById('country-name');
  const marketCountry = document.getElementById('market-country');
  for (const option of [...salesCountry.options].slice(1)) marketCountry.append(option.cloneNode(true));

  function showMarket() {
    const code = salesCountry.value;
    marketCountry.value = code;
    document.getElementById('market-empty').hidden = Boolean(code);
    for (const [id, visible] of [['market-gb', code === 'GB'], ['market-us', code === 'US'],
      ['market-in', code === 'IN'], ['market-other', Boolean(code) && !['GB','US','IN'].includes(code)]]) {
      document.getElementById(id).hidden = !visible;
    }
    if (code && !['GB','US','IN'].includes(code)) {
      document.getElementById('market-other-title').textContent = marketCountry.selectedOptions[0].textContent + ' · source coverage';
    }
  }

  salesCountry.addEventListener('change', showMarket);
  marketCountry.addEventListener('change', () => {
    salesCountry.value = marketCountry.value;
    salesCountry.dispatchEvent(new Event('change', {bubbles: true}));
  });
  showMarket();
}

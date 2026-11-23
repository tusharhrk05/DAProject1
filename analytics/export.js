// The main app is a classic script whose top-level `store` contains the
// browser's saved workspace. This export intentionally takes a read-only snapshot.
document.addEventListener('click', event => {
  const button = event.target.closest('[data-export-analytics]');
  if (!button) return;

  const snapshot = {
    appName: 'BahiPro',
    schemaVersion: 1,
    exportedAt: new Date().toISOString(),
    profile: store.profile,
    customers: store.customers,
    products: store.products,
    bills: store.bills,
    purchases: store.purchases
  };
  const date = new Date().toISOString().slice(0, 10);
  const url = URL.createObjectURL(new Blob(
    [JSON.stringify(snapshot, null, 2)],
    { type: 'application/json;charset=utf-8' }
  ));
  const link = document.createElement('a');
  link.href = url;
  link.download = `bahipro-analytics-${date}.json`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  if (typeof toast === 'function') toast('Analysis data export is ready.');
});

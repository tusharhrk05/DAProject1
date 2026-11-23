const BAHIPRO_SHEETS_CONFIG_KEY = 'bahipro-google-sheets-config-v1';
const BAHIPRO_SHEETS_CONFIG_OWNER_KEY = 'bahipro-google-sheets-config-owner-v1';
let bahiProSheetsSyncTimer = null;
let bahiProSheetsSyncInFlight = false;
let bahiProSheetsSyncQueued = false;

function bahiProSheetsConfigKey() {
  try {
    if (!localStorage.getItem(BAHIPRO_SHEETS_CONFIG_KEY)) {
      const ownerId = localStorage.getItem(BAHIPRO_SHEETS_CONFIG_OWNER_KEY);
      if (ownerId) {
        const previousConfig = localStorage.getItem(`${BAHIPRO_SHEETS_CONFIG_KEY}-${ownerId}`);
        if (previousConfig) localStorage.setItem(BAHIPRO_SHEETS_CONFIG_KEY, previousConfig);
      }
    }
  } catch (error) {}
  return BAHIPRO_SHEETS_CONFIG_KEY;
}

function readBahiProSheetsConfig() {
  try {
    return JSON.parse(localStorage.getItem(bahiProSheetsConfigKey()) || '{}');
  } catch (error) {
    return {};
  }
}

function openBahiProSheetsConfig() {
  const config = readBahiProSheetsConfig();
  const host = document.querySelector('#modal-content');
  host.innerHTML = `<h2 id="modal-title">Connect Google Sheets</h2>
    <p class="modal-intro">Add the Apps Script web app URL and the export token from your Google account setup.</p>
    <form id="google-sheets-config-form">
      <div class="form-field"><label for="google-sheets-url">Apps Script web app URL</label>
        <input class="field" id="google-sheets-url" type="url" required value="${escapeHtml(config.url || '')}" placeholder="https://script.google.com/macros/s/.../exec"></div>
      <div class="form-field"><label for="google-sheets-token">Export token</label>
        <input class="field" id="google-sheets-token" type="password" minlength="32" required value="${escapeHtml(config.token || '')}" autocomplete="new-password" placeholder="Your private token"></div>
      <p class="form-note">The token is stored in this browser. Keep it private. The one-time Apps Script setup is in analytics/README.md.</p>
      <div class="modal-actions"><button type="button" class="btn" data-close>Cancel</button><button type="submit" class="btn btn-primary">Save connection</button></div>
    </form>`;
  document.querySelector('#google-sheets-config-form').addEventListener('submit', event => {
    event.preventDefault();
    const urlText = document.querySelector('#google-sheets-url').value.trim();
    const token = document.querySelector('#google-sheets-token').value.trim();
    let parsedUrl;
    try {
      parsedUrl = new URL(urlText);
    } catch (error) {
      toast('Enter a valid Apps Script web app URL.');
      return;
    }
    if (parsedUrl.protocol !== 'https:' || parsedUrl.hostname !== 'script.google.com' ||
        !parsedUrl.pathname.includes('/macros/s/') || !parsedUrl.pathname.endsWith('/exec')) {
      toast('Use the HTTPS web app URL ending in /exec.');
      return;
    }
    if (token.length < 32) {
      toast('Use the 32+ character private token configured in Apps Script.');
      return;
    }
    try {
      localStorage.setItem(bahiProSheetsConfigKey(), JSON.stringify({ url: parsedUrl.href, token }));
    } catch (error) {
      toast('Could not save the Sheets connection in this browser.');
      return;
    }
    closeModal();
    toast('Google Sheets connection saved on this device.');
  });
  document.querySelector('#modal-backdrop').hidden = false;
  document.querySelector('.modal-close').focus();
}

function setBahiProSheetsSyncStatus(message, isError = false) {
  const status = document.querySelector('#save-status');
  if (!status) return;
  status.textContent = message;
  status.classList.toggle('save-error', isError);
}

function scheduleBahiProSheetsSync() {
  const config = readBahiProSheetsConfig();
  if (!config.url || !config.token) return;
  clearTimeout(bahiProSheetsSyncTimer);
  bahiProSheetsSyncTimer = setTimeout(() => {
    if (navigator.onLine === false) {
      setBahiProSheetsSyncStatus('Saved on device · will sync when online');
      return;
    }
    if (bahiProSheetsSyncInFlight) {
      bahiProSheetsSyncQueued = true;
      return;
    }
    exportBahiProToGoogleSheets({ automatic: true });
  }, 1200);
}

function makeBahiProExportId() {
  const bytes = new Uint8Array(16);
  if (window.crypto?.getRandomValues) window.crypto.getRandomValues(bytes);
  else for (let i = 0; i < bytes.length; i++) bytes[i] = Math.floor(Math.random() * 256);
  return [...bytes].map(value => value.toString(16).padStart(2, '0')).join('');
}

function pollBahiProSheetsResult(config, requestId) {
  return new Promise((resolve, reject) => {
    const callbackName = `__bahiproSheetsResult_${requestId}`;
    let attempts = 0;
    const check = () => {
      attempts++;
      const url = new URL(config.url);
      url.searchParams.set('action', 'status');
      url.searchParams.set('callback', callbackName);
      url.searchParams.set('id', requestId);
      const script = document.createElement('script');
      const cleanup = () => { script.remove(); };
      window[callbackName] = result => {
        cleanup();
        if (result?.pending && attempts < 20) {
          setTimeout(check, 900);
          return;
        }
        delete window[callbackName];
        if (result?.ok) resolve(result);
        else reject(new Error(result?.error || 'Google Sheets did not return an export result.'));
      };
      script.onerror = () => {
        cleanup();
        delete window[callbackName];
        reject(new Error('Could not reach the Google Sheets receiver. Check the deployed /exec URL.'));
      };
      script.src = url.href;
      document.head.appendChild(script);
      setTimeout(() => {
        if (window[callbackName] && attempts >= 20) {
          delete window[callbackName];
          cleanup();
          reject(new Error('Google Sheets did not respond in time. Check that the web app deployment is accessible.'));
        }
      }, 22000);
    };
    check();
  });
}

async function exportBahiProToGoogleSheets({ automatic = false } = {}) {
  const config = readBahiProSheetsConfig();
  if (!config.url || !config.token) {
    if (!automatic) openBahiProSheetsConfig();
    return;
  }
  if (bahiProSheetsSyncInFlight) {
    bahiProSheetsSyncQueued = true;
    return;
  }
  bahiProSheetsSyncInFlight = true;
  setBahiProSheetsSyncStatus(automatic ? 'Syncing to Google Sheets…' : 'Exporting to Google Sheets…');
  try {
    const requestId = makeBahiProExportId();
    const data = {
      appName: 'BahiPro',
      schemaVersion: 1,
      exportedAt: new Date().toISOString(),
      profile: store.profile,
      customers: store.customers,
      products: store.products,
      bills: store.bills,
      purchases: store.purchases
    };
    const payload = { requestId, token: config.token, data };
    await fetch(config.url, {
      method: 'POST',
      mode: 'no-cors',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' },
      body: new URLSearchParams({ payload: JSON.stringify(payload) })
    });
    const result = await pollBahiProSheetsResult(config, requestId);
    setBahiProSheetsSyncStatus(`✓ Sheets updated · ${result.updated?.length || 0} tabs`);
    if (!automatic) toast('Your reports are updated in Google Sheets.');
  } catch (error) {
    setBahiProSheetsSyncStatus('Google Sheets sync failed', true);
    if (!automatic) toast(error.message || 'Could not export to Google Sheets.');
  } finally {
    bahiProSheetsSyncInFlight = false;
    if (bahiProSheetsSyncQueued) {
      bahiProSheetsSyncQueued = false;
      scheduleBahiProSheetsSync();
    }
  }
}

document.addEventListener('click', event => {
  if (event.target.closest('[data-google-sheets-configure]')) openBahiProSheetsConfig();
  if (event.target.closest('[data-google-sheets-export]')) exportBahiProToGoogleSheets();
});
window.addEventListener('bahipro:store-saved', scheduleBahiProSheetsSync);
window.addEventListener('online', scheduleBahiProSheetsSync);
if (readBahiProSheetsConfig().url && readBahiProSheetsConfig().token) {
  setTimeout(scheduleBahiProSheetsSync, 1000);
}

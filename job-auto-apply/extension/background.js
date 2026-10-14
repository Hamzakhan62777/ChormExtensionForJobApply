const BACKEND_URL = "http://127.0.0.1:8000";

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "CALL_BACKEND") {
    fetch(`${BACKEND_URL}${message.endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(message.payload),
    })
      .then(async (res) => {
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          sendResponse({
            ok: false,
            error: data.detail || `Server returned status ${res.status}`,
          });
        } else {
          sendResponse({ ok: true, data });
        }
      })
      .catch(() => {
        sendResponse({
          ok: false,
          error:
            "Cannot connect to Python server at http://127.0.0.1:8000. Make sure 'python auto_apply_backend.py' is running in your terminal!",
        });
      });

    return true;
  }
});
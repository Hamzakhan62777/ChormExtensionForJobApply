var BACKEND_URL = "http://127.0.0.1:8000";
var EMAIL_REGEX = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g;
var lastSelectedText = "";

// Save highlighted text whenever you select text with your mouse
document.addEventListener("selectionchange", () => {
  const sel = window.getSelection().toString().trim();
  if (sel.length > 5) {
    lastSelectedText = sel;
  }
});

function showToast(message, isError = false) {
  let toast = document.getElementById("ai-autoapply-toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "ai-autoapply-toast";
    Object.assign(toast.style, {
      position: "fixed",
      bottom: "24px",
      right: "24px",
      zIndex: "999999",
      padding: "14px 20px",
      borderRadius: "10px",
      color: "#ffffff",
      fontFamily: "system-ui, -apple-system, sans-serif",
      fontSize: "14px",
      fontWeight: "600",
      boxShadow: "0 8px 24px rgba(0,0,0,0.25)",
      maxWidth: "420px",
      whiteSpace: "pre-line",
      transition: "opacity 0.3s ease",
    });
    document.body.appendChild(toast);
  }
  toast.style.background = isError ? "#dc2626" : "#059669";
  toast.textContent = message;
  toast.style.opacity = "1";

  clearTimeout(window.__autoApplyToastTimer);
  window.__autoApplyToastTimer = setTimeout(() => {
    toast.style.opacity = "0";
  }, 8000);
}

// 1. Automatically add a blue button under any LinkedIn post that has an email
function scanLinkedInFeedPosts() {
  const posts = document.querySelectorAll(
    ".feed-shared-update-v2, .occludable-update, [data-urn*='urn:li:activity']"
  );

  posts.forEach((post) => {
    if (post.dataset.autoApplyInjected === "true") return;

    const textContent = post.innerText || "";
    const matchedEmails = textContent.match(EMAIL_REGEX);
    if (!matchedEmails || matchedEmails.length === 0) return;

    post.dataset.autoApplyInjected = "true";
    const targetEmail = matchedEmails[0];

    const btn = document.createElement("button");
    btn.innerText = `⚡ Auto-Apply via Email (${targetEmail})`;
    Object.assign(btn.style, {
      display: "inline-flex",
      alignItems: "center",
      margin: "10px 16px",
      padding: "8px 16px",
      backgroundColor: "#0a66c2",
      color: "#ffffff",
      border: "none",
      borderRadius: "20px",
      fontSize: "13px",
      fontWeight: "600",
      cursor: "pointer",
    });

    btn.addEventListener("click", async (e) => {
      e.preventDefault();
      e.stopPropagation();

      const originalLabel = btn.innerText;
      btn.innerText = "⏳ Sending Email...";
      btn.disabled = true;

      try {
        const res = await fetch(`${BACKEND_URL}/apply-email`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            post_text: post.innerText,
            post_url: window.location.href,
            override_email: targetEmail,
          }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to send email");

        btn.innerText = `✅ Email Sent (${targetEmail})`;
        btn.style.backgroundColor = "#059669";
        showToast(`✅ ${data.message}\nSubject: ${data.subject}`);
      } catch (err) {
        btn.innerText = originalLabel;
        btn.disabled = false;
        showToast(`❌ ${err.message}`, true);
      }
    });

    post.appendChild(btn);
  });
}

// 2. Always show the green "📧 Email-Apply Selected Post" button in the bottom-left corner
function ensureFloatingButton() {
  if (!document.body || document.getElementById("ai-floating-job-apply-btn")) return;

  const container = document.createElement("div");
  container.id = "ai-floating-job-apply-btn";
  Object.assign(container.style, {
    position: "fixed",
    bottom: "24px",
    left: "24px",
    zIndex: "999999",
  });

  const emailSelectionBtn = document.createElement("button");
  emailSelectionBtn.innerText = "📧 Email-Apply Selected Post";
  Object.assign(emailSelectionBtn.style, {
    padding: "12px 18px",
    backgroundColor: "#059669",
    color: "#ffffff",
    border: "none",
    borderRadius: "24px",
    fontSize: "14px",
    fontWeight: "700",
    cursor: "pointer",
    boxShadow: "0 4px 14px rgba(0, 0, 0, 0.3)",
  });

  emailSelectionBtn.addEventListener("mousedown", (e) => {
    const currentSel = window.getSelection().toString().trim();
    if (currentSel) lastSelectedText = currentSel;
    e.preventDefault();
  });

  emailSelectionBtn.addEventListener("click", async () => {
    const selectedText = window.getSelection().toString().trim() || lastSelectedText;
    if (!selectedText) {
      showToast(
        "Highlight/select the LinkedIn post text (including the email address) with your mouse first, then click this button!",
        true
      );
      return;
    }

    emailSelectionBtn.innerText = "⏳ Sending Email...";
    emailSelectionBtn.disabled = true;
    try {
      const res = await fetch(`${BACKEND_URL}/apply-email`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          post_text: selectedText,
          post_url: window.location.href,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Email apply failed");
      showToast(`✅ ${data.message}\nSubject: ${data.subject}`);
    } catch (err) {
      showToast(`❌ ${err.message}`, true);
    } finally {
      emailSelectionBtn.innerText = "📧 Email-Apply Selected Post";
      emailSelectionBtn.disabled = false;
    }
  });

  container.appendChild(emailSelectionBtn);
  document.body.appendChild(container);
}

ensureFloatingButton();
setInterval(() => {
  ensureFloatingButton();
  scanLinkedInFeedPosts();
}, 1500);
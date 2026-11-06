"use strict";

// Give server-rendered forms immediate feedback and prevent duplicate submissions.
document.querySelectorAll("form[method='post']").forEach(form => {
  form.addEventListener("submit", event => {
    if (event.defaultPrevented || !form.checkValidity()) return;
    const button = event.submitter || form.querySelector("button[type='submit'], button:not([type])");
    if (!button) return;
    button.disabled = true;
    form.setAttribute("aria-busy", "true");
    button.dataset.originalLabel = button.textContent;
    button.textContent = form.action.includes("benchmark") || form.action.includes("batch-run")
      ? "Đang đo trên máy của bạn…" : "Đang xử lý…";
  });
});
window.addEventListener("pageshow", () => {
  document.querySelectorAll("button[data-original-label]").forEach(button => {
    button.textContent = button.dataset.originalLabel;
    button.disabled = false;
    button.closest("form")?.removeAttribute("aria-busy");
  });
});
// Existing report pages retain their routes, with the same table behavior on mobile.
document.querySelectorAll(".panel > table").forEach(table => {
  const wrapper = document.createElement("div");
  wrapper.className = "tablewrap";
  wrapper.tabIndex = 0;
  wrapper.setAttribute("aria-label", "Bảng số liệu, cuộn ngang để xem thêm cột");
  table.before(wrapper);
  wrapper.append(table);
});
const upload = document.querySelector("#csv-file");
if (upload) {
  upload.addEventListener("change", () => {
    const file = upload.files[0];
    upload.setCustomValidity(file && file.size > 12 * 1024 * 1024
      ? "File CSV phải nhỏ hơn 12 MB." : "");
    const label = document.querySelector("#upload-filename");
    if (label) label.textContent = file ? file.name : "CSV UTF-8 · Tối đa 12 MB";
  });
}

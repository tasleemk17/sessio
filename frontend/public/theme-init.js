// Applies the saved theme before the first paint so a dark-mode user never sees a white flash.
// Kept as a file, not inline in index.html, so the Content-Security-Policy can forbid inline scripts.
try {
  if (localStorage.getItem("sessio.theme") === "dark") document.documentElement.classList.add("dark");
} catch (e) {}

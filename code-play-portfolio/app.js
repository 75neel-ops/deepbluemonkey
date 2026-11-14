// Keep the displayed year current while retaining 2026 in a no-JavaScript fallback.
document.getElementById("year").textContent = String(new Date().getFullYear());


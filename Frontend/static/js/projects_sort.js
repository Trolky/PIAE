(function () {
  function getCellText(cell) {
    return (cell?.textContent || "").trim();
  }

  const STATE_RANK = {
    COMPLETED: 0,
    ASSIGNED: 1,
    APPROVED: 2,
    CLOSED: 3,
    CREATED: 4,
  };

  function parseIsoDate(value) {
    const t = Date.parse(value);
    return Number.isFinite(t) ? t : null;
  }

  function compare(a, b) {
    if (a === b) return 0;
    if (a === "" || a == null) return 1;
    if (b === "" || b == null) return -1;
    return a < b ? -1 : 1;
  }

  function makeComparator(colKey, dir) {
    const mul = dir === "desc" ? -1 : 1;

    return function (rowA, rowB) {
      const a = rowA.dataset;
      const b = rowB.dataset;

      let c = 0;

      if (colKey === "state") {
        c = compare(STATE_RANK[a.state] ?? 999, STATE_RANK[b.state] ?? 999);
      } else if (colKey === "file") {
        c = compare(a.file || "", b.file || "");
      } else if (colKey === "language") {
        c = compare(a.language || "", b.language || "");
      } else if (colKey === "created") {
        const da = parseIsoDate(a.created) ?? -1;
        const db = parseIsoDate(b.created) ?? -1;
        c = compare(da, db);
      } else if (colKey === "customer") {
        c = compare(a.customer || "", b.customer || "");
      } else if (colKey === "translator") {
        c = compare(a.translator || "", b.translator || "");
      }

      if (c === 0) {
        // stabilní fallback: file, created
        c = compare(a.file || "", b.file || "");
        if (c === 0) c = compare(parseIsoDate(a.created) ?? -1, parseIsoDate(b.created) ?? -1);
      }

      return c * mul;
    };
  }

  function setHeaderState(ths, activeKey, activeDir) {
    ths.forEach((th) => {
      const key = th.dataset.sortKey;
      if (!key) return;
      th.classList.toggle("table__th--sortable", true);
      th.classList.toggle("table__th--active", key === activeKey);
      th.dataset.sortDir = key === activeKey ? activeDir : "";

      const label = th.querySelector(".table__th-label");
      if (label) {
        label.dataset.dir = key === activeKey ? activeDir : "";
      }
    });
  }

  function init(table) {
    const tbody = table.querySelector("tbody");
    if (!tbody) return;

    const rows = Array.from(tbody.querySelectorAll("tr"));

    // default sort: state rank (Completed -> Assigned -> Approved -> Closed -> Created), potom created desc
    rows.sort((ra, rb) => {
      const a = ra.dataset;
      const b = rb.dataset;
      const r = compare(STATE_RANK[a.state] ?? 999, STATE_RANK[b.state] ?? 999);
      if (r !== 0) return r;
      // created desc
      const da = parseIsoDate(a.created) ?? -1;
      const db = parseIsoDate(b.created) ?? -1;
      return compare(da, db) * -1;
    });

    rows.forEach((r) => tbody.appendChild(r));

    let currentKey = "state";
    let currentDir = "asc";

    const headers = Array.from(table.querySelectorAll("thead th[data-sort-key]"));
    setHeaderState(headers, currentKey, currentDir);

    headers.forEach((th) => {
      th.addEventListener("click", () => {
        const key = th.dataset.sortKey;
        if (!key) return;

        if (currentKey === key) {
          currentDir = currentDir === "asc" ? "desc" : "asc";
        } else {
          currentKey = key;
          currentDir = "asc";
        }

        const rs = Array.from(tbody.querySelectorAll("tr"));
        rs.sort(makeComparator(currentKey, currentDir));
        rs.forEach((r) => tbody.appendChild(r));

        setHeaderState(headers, currentKey, currentDir);
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    const table = document.querySelector("table[data-projects-table]");
    if (table) init(table);
  });
})();


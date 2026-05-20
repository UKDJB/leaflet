(function () {
  const listEl = document.getElementById("family-list");
  const searchEl = document.getElementById("family-search");
  const metaEl = document.getElementById("family-meta");
  const selectionEl = document.getElementById("selection-label");
  const printBtn = document.getElementById("print-btn");
  const frameEl = document.getElementById("sheet-frame");
  const emptyEl = document.getElementById("preview-empty");

  /** @type {{ id: string, xref: string, label: string, lineage?: boolean }[]} */
  let families = [];
  let selectedId = null;

  function setMeta(text) {
    metaEl.textContent = text;
  }

  function setSelection(label) {
    selectionEl.textContent = label || "No family selected";
    printBtn.disabled = !selectedId;
  }

  function setPreviewLoaded(loaded) {
    frameEl.classList.toggle("is-loaded", loaded);
    emptyEl.classList.toggle("is-hidden", loaded);
  }

  function renderList(filter) {
    const needle = (filter || "").trim().toLowerCase();
    listEl.innerHTML = "";
    const visible = families.filter(function (f) {
      if (!needle) return true;
      return (
        f.label.toLowerCase().includes(needle) ||
        f.id.toLowerCase().includes(needle)
      );
    });

    if (!visible.length) {
      const li = document.createElement("li");
      li.className = "leaflet-family-item";
      li.textContent = needle ? "No families match your search." : "No families loaded.";
      listEl.appendChild(li);
      setMeta(needle ? "0 matches" : "");
      return;
    }

    visible.forEach(function (fam) {
      const li = document.createElement("li");
      li.className = "leaflet-family-item";
      li.setAttribute("role", "option");

      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "leaflet-family-item__btn";
      if (fam.lineage) {
        btn.appendChild(document.createTextNode(fam.label));
        const star = document.createElement("span");
        star.className = "leaflet-family-item__star";
        star.setAttribute("aria-hidden", "true");
        star.textContent = " ★";
        btn.appendChild(star);
      } else {
        btn.textContent = fam.label;
      }
      btn.dataset.familyId = fam.id;
      if (fam.id === selectedId) {
        btn.classList.add("is-selected");
        btn.setAttribute("aria-selected", "true");
      }

      btn.addEventListener("click", function () {
        selectFamily(fam.id, fam.label);
      });

      li.appendChild(btn);
      listEl.appendChild(li);
    });

    const total = families.length;
    const shown = visible.length;
    setMeta(
      shown === total
        ? total + " families"
        : shown + " of " + total + " families"
    );
  }

  function selectFamily(id, label) {
    selectedId = id;
    setSelection(label);
    setPreviewLoaded(false);
    frameEl.src = "/api/family/" + encodeURIComponent(id) + "/sheet";
    frameEl.onload = function () {
      setPreviewLoaded(true);
    };
    renderList(searchEl.value);
  }

  printBtn.addEventListener("click", function () {
    if (!selectedId || !frameEl.contentWindow) return;
    try {
      frameEl.contentWindow.focus();
      frameEl.contentWindow.print();
    } catch (err) {
      window.alert("Could not open print dialog. Try selecting the family again.");
    }
  });

  searchEl.addEventListener("input", function () {
    renderList(searchEl.value);
  });

  setMeta("Loading families…");
  fetch("/api/families")
    .then(function (res) {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.json();
    })
    .then(function (data) {
      families = data.families || [];
      renderList("");
      if (!families.length) {
        setMeta("No families in GEDCOM.");
      }
    })
    .catch(function (err) {
      setMeta("Failed to load families.");
      listEl.innerHTML =
        '<li class="leaflet-family-item">Error: ' +
        String(err.message || err) +
        "</li>";
    });
})();

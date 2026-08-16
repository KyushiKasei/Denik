(function () {
  let map = null;
  let layoutTimer = 0;
  let resizeObserver = null;

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function destroyMap() {
    if (layoutTimer) {
      clearTimeout(layoutTimer);
      layoutTimer = 0;
    }
    if (resizeObserver) {
      resizeObserver.disconnect();
      resizeObserver = null;
    }
    if (map) {
      map.remove();
      map = null;
    }
  }

  function readMapData() {
    const node = document.getElementById("nearby-map-data");
    if (!node) {
      return null;
    }
    try {
      return JSON.parse(node.textContent || "");
    } catch (_err) {
      return null;
    }
  }

  function initMap(el, data) {
    destroyMap();
    if (!el || !data || typeof L === "undefined") {
      return;
    }
    const lat = Number(data.lat);
    const lon = Number(data.lon);
    const radiusKm = Number(data.radius);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
      return;
    }
    const iconBase = "/static/vendor/leaflet/images/";
    L.Icon.Default.mergeOptions({
      iconUrl: iconBase + "marker-icon.png",
      iconRetinaUrl: iconBase + "marker-icon-2x.png",
      shadowUrl: iconBase + "marker-shadow.png",
    });
    const markers = Array.isArray(data.markers) ? data.markers : [];
    const instance = L.map(el, {
      zoomControl: true,
      scrollWheelZoom: true,
      center: [lat, lon],
      zoom: 11,
    });
    map = instance;
    const tiles = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap",
      maxZoom: 19,
    }).addTo(instance);
    tiles.on("tileerror", function () {
      const wrap = document.getElementById("nearby-map-wrap");
      if (!wrap || wrap.querySelector(".nearby-map-error")) {
        return;
      }
      const note = document.createElement("p");
      note.className = "muted nearby-map-error";
      note.textContent = "Mapové podklady se nenačetly. Značky míst z katalogu by měly jít vidět.";
      wrap.appendChild(note);
    });
    L.marker([lat, lon]).addTo(instance).bindPopup("Tady");
    const circle = L.circle([lat, lon], {
      radius: radiusKm * 1000,
      color: "#3d5a40",
      fillOpacity: 0.08,
    }).addTo(instance);
    markers.forEach(function (item) {
      if (item.lat == null || item.lon == null) {
        return;
      }
      const color = item.visited ? "#3d5a40" : item.want ? "#c9a227" : "#6a6258";
      L.circleMarker([item.lat, item.lon], {
        radius: 7,
        color: color,
        fillColor: color,
        fillOpacity: 0.9,
      })
        .addTo(instance)
        .bindPopup(
          "<a href=\"/places/" +
            encodeURIComponent(item.id) +
            "\">" +
            escapeHtml(item.name) +
            "</a><br>" +
            Number(item.km).toFixed(1) +
            " km"
        );
    });

    function layout() {
      if (map !== instance || !el.isConnected) {
        return;
      }
      instance.invalidateSize();
      instance.fitBounds(circle.getBounds(), { padding: [16, 16], maxZoom: 14 });
    }
    layout();
    requestAnimationFrame(function () {
      requestAnimationFrame(layout);
    });
    layoutTimer = setTimeout(layout, 200);
    if (typeof ResizeObserver !== "undefined") {
      resizeObserver = new ResizeObserver(function () {
        if (map === instance) {
          instance.invalidateSize();
        }
      });
      resizeObserver.observe(el);
    }
  }

  function syncMap() {
    const wrap = document.getElementById("nearby-map-wrap");
    const el = document.getElementById("nearby-map");
    const data = readMapData();
    if (!wrap || !el || !data) {
      destroyMap();
      if (wrap) {
        wrap.hidden = true;
      }
      return;
    }
    wrap.hidden = false;
    initMap(el, data);
  }

  function resultsSwapped(event) {
    const target = event.detail && event.detail.target;
    return !!(target && target.id === "nearby-results");
  }

  function bind() {
    const form = document.getElementById("nearby-form");
    const slider = document.getElementById("nearby-radius");
    const label = document.getElementById("nearby-radius-label");
    const gpsBtn = document.getElementById("nearby-gps");
    if (slider && label) {
      slider.addEventListener("input", function () {
        label.textContent = slider.value;
      });
    }
    const qInput = document.getElementById("nearby-q");
    if (qInput) {
      qInput.addEventListener("input", function () {
        const lat = document.getElementById("nearby-lat");
        const lon = document.getElementById("nearby-lon");
        const originLabel = document.getElementById("nearby-origin-label");
        if (lat) lat.value = "";
        if (lon) lon.value = "";
        if (originLabel) originLabel.value = "";
      });
    }
    if (gpsBtn) {
      gpsBtn.addEventListener("click", function () {
        const errorEl = document.getElementById("nearby-gps-error");
        function showGpsError(message) {
          if (!errorEl) {
            return;
          }
          errorEl.hidden = !message;
          errorEl.textContent = message || "";
        }
        showGpsError("");
        if (!navigator.geolocation) {
          showGpsError("Prohlížeč GPS nenabízí. Zadejte obec, nebo souřadnice.");
          return;
        }
        gpsBtn.disabled = true;
        navigator.geolocation.getCurrentPosition(
          function (pos) {
            const lat = document.getElementById("nearby-lat");
            const lon = document.getElementById("nearby-lon");
            if (lat && lon) {
              lat.value = pos.coords.latitude.toFixed(6);
              lon.value = pos.coords.longitude.toFixed(6);
            }
            const originLabel = document.getElementById("nearby-origin-label");
            if (originLabel) {
              originLabel.value = "Moje poloha";
            }
            gpsBtn.disabled = false;
            if (form) {
              form.requestSubmit();
            }
          },
          function (err) {
            gpsBtn.disabled = false;
            if (err && err.code === err.PERMISSION_DENIED) {
              showGpsError("Přístup k poloze byl odepřen. Zadejte obec, nebo souřadnice.");
              return;
            }
            showGpsError("Polohu se nepodařilo zjistit. Zadejte obec, nebo souřadnice.");
          }
        );
      });
    }
    document.body.addEventListener("click", function (event) {
      const link = event.target.closest("#nearby-suggest a");
      if (!link) {
        return;
      }
      const box = document.getElementById("nearby-suggest");
      if (box) {
        box.innerHTML = "";
      }
    });
    syncMap();
  }

  document.body.addEventListener("htmx:afterSettle", function (event) {
    if (resultsSwapped(event)) {
      syncMap();
    }
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bind);
  } else {
    bind();
  }
})();
